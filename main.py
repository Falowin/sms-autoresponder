import logging
import re
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Bot, Update
from telegram.ext import Application

import ai
import db
import bot as mod_bot
from config import load_config
from sms import normalize_phone

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

config = load_config()
mod_app: Application = None


# ─── Lead parser ────────────────────────────────────────────────────────────

def parse_lead(text: str) -> dict | None:
    """Parse incoming Telegram lead message into structured data.

    Supports emoji-based format:
        🔵 Новый лид #N
        👤 Name
        📞 Phone
        ✉️  Email
        🛠  Service
        📍 Источник: ...
        💬 Message (may be multiline)
        🔗 CRM: url

    Also supports legacy key-value format:
        Name: ...  Phone: ...  etc.
    """
    result = {}

    # ── Emoji format ──────────────────────────────────────────────────────────
    m = re.search(r"👤\s*(.+)", text)
    if m:
        result["name"] = m.group(1).strip()

    m = re.search(r"📞\s*(.+)", text)
    if m:
        result["phone"] = m.group(1).strip()

    m = re.search(r"✉️\s*(.+)", text)
    if m:
        result["email"] = m.group(1).strip()

    m = re.search(r"🛠\s*(.+)", text)
    if m:
        result["service"] = m.group(1).strip()

    # Message: everything after 💬 up to (but not including) the 🔗 line
    m = re.search(r"💬\s*(.+?)(?=\n🔗|\Z)", text, re.DOTALL)
    if m:
        result["message"] = m.group(1).strip()

    # ── Legacy key-value format (fallback) ───────────────────────────────────
    if not result.get("name"):
        m = re.search(r"Name:\s*(.+)", text, re.IGNORECASE)
        if m:
            result["name"] = m.group(1).strip()

    if not result.get("phone"):
        m = re.search(r"Phone:\s*(.+)", text, re.IGNORECASE)
        if m:
            result["phone"] = m.group(1).strip()

    if not result.get("email"):
        m = re.search(r"Email:\s*(.+)", text, re.IGNORECASE)
        if m:
            result["email"] = m.group(1).strip()

    if not result.get("service"):
        m = re.search(r"Service:\s*(.+)", text, re.IGNORECASE)
        if m:
            result["service"] = m.group(1).strip()

    if not result.get("message"):
        m = re.search(r"Message:\s*(.+)", text, re.IGNORECASE)
        if m:
            result["message"] = m.group(1).strip()

    if not result.get("phone") or not result.get("name"):
        return None
    return result


# ─── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global mod_app

    # Init DB
    await db.init_db(config.database_path)

    # Init and start moderation bot (webhook mode)
    mod_app = mod_bot.build_mod_app(config)
    await mod_app.initialize()
    await mod_app.bot.set_webhook(
        url=f"{config.webhook_base_url}/telegram/mod/webhook"
    )
    await mod_app.start()

    # Set lead bot webhook
    lead_bot = Bot(token=config.telegram_lead_bot_token)
    await lead_bot.delete_webhook(drop_pending_updates=True)
    await lead_bot.set_webhook(
        url=f"{config.webhook_base_url}/telegram/lead/webhook",
        allowed_updates=["message", "channel_post", "edited_message", "edited_channel_post"],
    )

    logger.info("✅ Bots started, webhooks set")
    yield

    # Cleanup
    await mod_app.stop()
    await mod_app.shutdown()


app = FastAPI(lifespan=lifespan)


# ─── Lead bot webhook ────────────────────────────────────────────────────────

@app.post("/telegram/lead/webhook")
async def lead_webhook(request: Request):
    data = await request.json()
    # Handle direct messages, channel posts, and group messages
    msg = (
        data.get("message")
        or data.get("channel_post")
        or data.get("edited_message")
        or data.get("edited_channel_post")
        or {}
    )
    text = msg.get("text", "")
    logger.info(f"Lead webhook: update_keys={list(data.keys())}, text_len={len(text)}, preview={text[:80]!r}")

    text_lower = text.lower()
    is_lead = (
        "new request:" in text_lower
        or "новый лид" in text_lower
        or "👤" in text  # emoji format always has name emoji
    )
    if not is_lead:
        return Response("ok")

    lead = parse_lead(text)
    if not lead:
        logger.warning("Could not parse lead from message")
        return Response("ok")

    phone = normalize_phone(lead["phone"])
    lead["phone"] = phone

    # Save conversation
    await db.upsert_conversation(
        config.database_path, phone, lead["name"], lead["email"],
        lead["service"], lead["message"]
    )

    # Generate 3 AI variants (2 natural + 1 sales)
    try:
        variants = await ai.generate_variants(
            config.anthropic_api_key,
            lead["name"],
            lead["service"],
            lead["message"],
        )
    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        variants = [
            f"Hi {lead['name']}! Thanks for reaching out about your {lead['service']}. We'd love to help! What's the best time for a cleaning?",
            f"Hello {lead['name']}! We specialize in {lead['service']} cleaning. When would be a good time to schedule? We're available 7 days a week!",
        ]

    # Save variants to DB and collect their IDs
    variant_ids = []
    for v in variants:
        vid = await db.save_variant(config.database_path, phone, v)
        variant_ids.append(vid)

    # Send to moderation bot with copy buttons
    try:
        await mod_bot.send_lead_with_variants(
            mod_app.bot, config, lead, variants, variant_ids
        )
    except Exception as e:
        logger.error(f"Failed to send lead to mod bot: {e}")

    return Response("ok")


# ─── Moderation bot webhook ──────────────────────────────────────────────────

@app.post("/telegram/mod/webhook")
async def mod_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, mod_app.bot)
    await mod_app.process_update(update)
    return Response("ok")


# ─── Health check ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Debug: webhook info & reset ─────────────────────────────────────────────

@app.get("/debug/webhook-info")
async def debug_webhook_info():
    lead_bot = Bot(token=config.telegram_lead_bot_token)
    info = await lead_bot.get_webhook_info()
    return {
        "url": info.url,
        "has_custom_certificate": info.has_custom_certificate,
        "pending_update_count": info.pending_update_count,
        "last_error_date": str(info.last_error_date) if info.last_error_date else None,
        "last_error_message": info.last_error_message,
        "max_connections": info.max_connections,
        "allowed_updates": info.allowed_updates,
    }


@app.post("/debug/reset-webhook")
async def debug_reset_webhook():
    lead_bot = Bot(token=config.telegram_lead_bot_token)
    await lead_bot.delete_webhook(drop_pending_updates=True)
    await lead_bot.set_webhook(
        url=f"{config.webhook_base_url}/telegram/lead/webhook",
        allowed_updates=["message", "channel_post", "edited_message", "edited_channel_post"],
    )
    info = await lead_bot.get_webhook_info()
    return {
        "status": "reset",
        "url": info.url,
        "pending_update_count": info.pending_update_count,
        "last_error_message": info.last_error_message,
    }


# ─── Debug: test AI ──────────────────────────────────────────────────────────

@app.get("/debug/test-ai")
async def debug_test_ai():
    import time
    start = time.time()
    try:
        variants = await ai.generate_variants(
            config.anthropic_api_key, "TestName", "couch", "need cleaning"
        )
        return {"ok": True, "count": len(variants), "elapsed": round(time.time() - start, 2), "sample": variants[0][:80]}
    except Exception as e:
        return {"ok": False, "error": str(e), "type": type(e).__name__, "elapsed": round(time.time() - start, 2)}


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.port, reload=False)
