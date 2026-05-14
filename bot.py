import html
import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, ContextTypes

import db
from config import Config

logger = logging.getLogger(__name__)


def _e(text: str) -> str:
    """Escape text for HTML parse mode."""
    return html.escape(str(text))


async def send_lead_with_variants(bot: Bot, config: Config, lead: dict,
                                   variants: list[str], variant_ids: list[str]):
    """Send lead info + AI variants to the moderation chat with copy buttons."""
    phone = lead.get("phone", "")
    name = lead.get("name", "")
    service = lead.get("service", "")
    message = lead.get("message", "")
    email = lead.get("email", "")

    lines = [
        "🔔 <b>Новый лид!</b>",
        "",
        f"👤 <b>Имя:</b> {_e(name)}",
        f"📱 <b>Телефон:</b> <code>{_e(phone)}</code>",
    ]
    if email:
        lines.append(f"📧 <b>Email:</b> {_e(email)}")
    lines += [
        f"🛋 <b>Услуга:</b> {_e(service)}",
        f"💬 <b>Сообщение:</b> {_e(message)}",
        "",
        "━━━━━━━━━━━━━━━━━",
    ]

    labels = ["Вариант 1", "Вариант 2", "🔥 Продажный"]
    for i, variant in enumerate(variants, 1):
        label = labels[i - 1] if i <= len(labels) else f"Вариант {i}"
        lines += [
            f"<b>{label}:</b>",
            _e(variant),
            "",
        ]

    lines.append("👇 Нажми кнопку — бот пришлёт текст для копирования:")

    text = "\n".join(lines)

    btn_labels = ["📋 Вариант 1", "📋 Вариант 2", "🔥 Продажный"]
    buttons = [
        [InlineKeyboardButton(
            btn_labels[i - 1] if i <= len(btn_labels) else f"📋 Вариант {i}",
            callback_data=f"copy:{vid}"
        )]
        for i, vid in enumerate(variant_ids, 1)
    ]
    keyboard = InlineKeyboardMarkup(buttons)

    await bot.send_message(
        chat_id=config.telegram_mod_chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=keyboard,
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Отправляю текст для копирования...")

    data = query.data
    config: Config = context.bot_data["config"]

    if data.startswith("copy:"):
        vid = data.split(":", 1)[1]
        text = await db.get_variant(config.database_path, vid)

        if not text:
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="⚠️ Вариант не найден (возможно устарел).",
            )
            return

        # Send the plain text as a new message — easy to long-press and copy
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=text,
        )


def build_mod_app(config: Config) -> Application:
    app = Application.builder().token(config.telegram_mod_bot_token).build()
    app.bot_data["config"] = config
    app.add_handler(CallbackQueryHandler(handle_callback))
    return app
