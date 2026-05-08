import os
from dataclasses import dataclass


@dataclass
class Config:
    # Telegram
    telegram_lead_bot_token: str
    telegram_mod_bot_token: str
    telegram_mod_chat_id: int

    # Anthropic
    anthropic_api_key: str

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

    # App
    webhook_base_url: str
    database_path: str = "conversations.db"
    port: int = 8000
    reminder_seconds: int = 55  # remind moderator before 60s window closes


def load_config() -> Config:
    required = [
        "TELEGRAM_LEAD_BOT_TOKEN",
        "TELEGRAM_MOD_BOT_TOKEN",
        "TELEGRAM_MOD_CHAT_ID",
        "ANTHROPIC_API_KEY",
        "TWILIO_ACCOUNT_SID",
        "TWILIO_AUTH_TOKEN",
        "TWILIO_PHONE_NUMBER",
        "WEBHOOK_BASE_URL",
    ]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise EnvironmentError(f"Missing required env vars: {', '.join(missing)}")

    return Config(
        telegram_lead_bot_token=os.environ["TELEGRAM_LEAD_BOT_TOKEN"],
        telegram_mod_bot_token=os.environ["TELEGRAM_MOD_BOT_TOKEN"],
        telegram_mod_chat_id=int(os.environ["TELEGRAM_MOD_CHAT_ID"]),
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        twilio_account_sid=os.environ["TWILIO_ACCOUNT_SID"],
        twilio_auth_token=os.environ["TWILIO_AUTH_TOKEN"],
        twilio_phone_number=os.environ["TWILIO_PHONE_NUMBER"],
        webhook_base_url=os.environ["WEBHOOK_BASE_URL"].rstrip("/"),
        database_path=os.getenv("DATABASE_PATH", "conversations.db"),
        port=int(os.getenv("PORT", "8000")),
        reminder_seconds=int(os.getenv("REMINDER_SECONDS", "55")),
    )
