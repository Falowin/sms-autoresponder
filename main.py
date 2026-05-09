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
    """Parse incoming Telegram lead message into structured data."""
    patterns = {
        "name":    r"Name:\s*(.+)",
        "phone":   r"Phone:\s*(.+)",
        "email":   r"Email:\s*(.+)",
        "service": r"Service:\s*(.+)",
        "message": r"Message:\s*(.+)",
    }
    result = {}
    for key, pattern in patterns.items():
        m = re.search(pattern, text, re.IGNORECASE)
        result[key] = m.group(1).strip() if m else ""

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

    if "New Request:" not in text and "new request:" not in text.lower():
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

    # Generate 2 AI variants
    try:
        variants = await ai.generate_variants(
            config.anthropic_api_key,
            lead["name"],
            lead["service"],
            lead["message"],
            n=2,
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
    await mod_bot.send_lead_with_variants(
        mod_app.bot, config, lead, variants, variant_ids
    )

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


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.port, reload=False)
