import asyncio
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters, ContextTypes

import db
import sms as sms_module
from config import Config

logger = logging.getLogger(__name__)

# State tracking for edit mode: chat_id -> pending_id
_edit_state: dict[int, int] = {}


def build_moderation_text(pending_id: int, conv: dict, draft: str,
                           direction: str, client_text: str = "") -> str:
    icon = "🆕 NEW LEAD" if direction == "outbound" else "💬 CLIENT REPLY"
    lines = [
        f"{icon}",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"👤 {conv['name']}",
        f"📞 {conv['phone']}",
        f"🛋 Service: {conv['service']}",
    ]
    if client_text:
        lines.append(f"📩 Client said: \"{client_text}\"")
    lines += [
        f"━━━━━━━━━━━━━━━━━━━━",
        f"📝 Proposed SMS:",
        f"",
        draft,
        f"",
        f"━━━━━━━━━━━━━━━━━━━━",
        f"⏱ Approve within 55 sec to hit the 1-min window!",
    ]
    return "\n".join(lines)


def approval_keyboard(pending_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Send", callback_data=f"send:{pending_id}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{pending_id}"),
        ]
    ])


async def send_for_moderation(bot: Bot, config: Config, pending_id: int,
                               conv: dict, draft: str, direction: str,
                               client_text: str = "") -> int:
    text = build_moderation_text(pending_id, conv, draft, direction, client_text)
    msg = await bot.send_message(
        chat_id=config.telegram_mod_chat_id,
        text=text,
        reply_markup=approval_keyboard(pending_id),
    )
    # Schedule reminder
    asyncio.create_task(
        _reminder(bot, config, pending_id, msg.message_id)
    )
    return msg.message_id


async def _reminder(bot: Bot, config: Config, pending_id: int, message_id: int):
    await asyncio.sleep(config.reminder_seconds)
    # Check if still pending
    pending = await db.get_pending(config.database_path, pending_id)
    if pending:
        try:
            await bot.send_message(
                chat_id=config.telegram_mod_chat_id,
                text=f"⚠️ REMINDER: Lead #{pending_id} still waiting for approval! "
                     f"Less than 5 seconds left for the 1-min window!",
                reply_to_message_id=message_id,
            )
        except Exception as e:
            logger.error(f"Reminder failed: {e}")


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    config: Config = context.bot_data["config"]

    if data.startswith("send:"):
        pending_id = int(data.split(":")[1])
        pending = await db.get_pending(config.database_path, pending_id)
        if not pending:
            await query.edit_message_text("⚠️ This message was already processed.")
            return

        phone = pending["phone"]
        draft = pending["draft_text"]

        # Send SMS
        try:
            sms_module.send_sms(
                config.twilio_account_sid,
                config.twilio_auth_token,
                config.twilio_phone_number,
                phone,
                draft,
            )
        except Exception as e:
            await query.edit_message_text(f"❌ SMS send failed: {e}")
            return

        # Save to history and clean up
        await db.append_history(config.database_path, phone, "assistant", draft)
        await db.update_status(config.database_path, phone, "active")
        await db.delete_pending(config.database_path, pending_id)

        await query.edit_message_text(
            query.message.text + "\n\n✅ SMS sent!"
        )

    elif data.startswith("edit:"):
        pending_id = int(data.split(":")[1])
        pending = await db.get_pending(config.database_path, pending_id)
        if not pending:
            await query.edit_message_text("⚠️ This message was already processed.")
            return

        chat_id = query.message.chat_id
        _edit_state[chat_id] = pending_id

        await context.bot.send_message(
            chat_id=chat_id,
            text="✏️ Write your custom SMS text (reply to this message):",
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    config: Config = context.bot_data["config"]

    if chat_id not in _edit_state:
        return

    pending_id = _edit_state.pop(chat_id)
    pending = await db.get_pending(config.database_path, pending_id)
    if not pending:
        await update.message.reply_text("⚠️ This message was already processed.")
        return

    custom_text = update.message.text
    phone = pending["phone"]

    # Send custom SMS
    try:
        sms_module.send_sms(
            config.twilio_account_sid,
            config.twilio_auth_token,
            config.twilio_phone_number,
            phone,
            custom_text,
        )
    except Exception as e:
        await update.message.reply_text(f"❌ SMS send failed: {e}")
        return

    await db.append_history(config.database_path, phone, "assistant", custom_text)
    await db.update_status(config.database_path, phone, "active")
    await db.delete_pending(config.database_path, pending_id)

    await update.message.reply_text("✅ Custom SMS sent!")


def build_mod_app(config: Config) -> Application:
    app = Application.builder().token(config.telegram_mod_bot_token).build()
    app.bot_data["config"] = config
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app
