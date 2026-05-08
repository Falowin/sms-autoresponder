import asyncio
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
    await lead_bot.set_webhook(
        url=f"{config.webhook_base_url}/telegram/lead/webhook"
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
    text = data.get("message", {}).get("text", "")

    if "New Request:" not in text and "new request:" not in text.lower():
        return Response("ok")

    lead = parse_lead(text)
    if not lead:
        logger.warning("Could not parse lead from message")
        return Response("ok")

    phone = normalize_phone(lead["phone"])
    name = lead["name"]
    service = lead["service"]
    client_message = lead["message"]

    # Save conversation
    await db.upsert_conversation(
        config.database_path, phone, name, lead["email"], service, client_message
    )

    # Generate AI draft
    try:
        draft = await ai.generate_first_response(
            config.anthropic_api_key, name, service, client_message
        )
    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        draft = f"Hi {name}! Thanks for reaching out about your {service}. We'd love to help! What's the best time for us to schedule the cleaning?"

    # Save as pending
    pending_id = await db.save_pending(
        config.database_path, phone, "outbound", draft
    )

    # Get conversation for moderation message
    conv = await db.get_conversation(config.database_path, phone)

    # Send to moderation bot
    bot_instance = mod_app.bot
    await mod_bot.send_for_moderation(
        bot_instance, config, pending_id, conv, draft, "outbound"
    )

    return Response("ok")


# ─── Moderation bot webhook ──────────────────────────────────────────────────

@app.post("/telegram/mod/webhook")
async def mod_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, mod_app.bot)
    await mod_app.process_update(update)
    return Response("ok")


# ─── Twilio incoming SMS ─────────────────────────────────────────────────────

@app.post("/twilio/incoming")
async def twilio_incoming(request: Request):
    form = await request.form()
    from_number = normalize_phone(form.get("From", ""))
    body = form.get("Body", "").strip()

    if not from_number or not body:
        return Response("", media_type="text/xml")

    conv = await db.get_conversation(config.database_path, from_number)
    if not conv:
        logger.warning(f"Received SMS from unknown number: {from_number}")
        return Response("", media_type="text/xml")

    # Save client message to history
    await db.append_history(config.database_path, from_number, "user", body)

    # Generate AI reply
    updated_conv = await db.get_conversation(config.database_path, from_number)
    try:
        draft = await ai.generate_reply(
            config.anthropic_api_key,
            conv["name"],
            conv["service"],
            updated_conv["history"],
            body,
        )
    except Exception as e:
        logger.error(f"AI reply generation failed: {e}")
        draft = f"Hi {conv['name']}! Thanks for your message. We'll get back to you shortly."

    # Save as pending
    pending_id = await db.save_pending(
        config.database_path, from_number, "inbound_reply", draft
    )

    # Send to moderation
    await mod_bot.send_for_moderation(
        mod_app.bot, config, pending_id, updated_conv,
        draft, "inbound_reply", client_text=body
    )

    # Return empty TwiML (we send reply manually after moderation)
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="text/xml"
    )


# ─── Twilio status callback ──────────────────────────────────────────────────

@app.post("/twilio/status")
async def twilio_status(request: Request):
    form = await request.form()
    logger.info(f"SMS status: {form.get('MessageStatus')} for {form.get('To')}")
    return Response("ok")


# ─── Health check ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=config.port, reload=False)
