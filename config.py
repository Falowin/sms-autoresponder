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

    # App
    webhook_base_url: str
    database_path: str = "conversations.db"
    port: int = 8000


def load_config() -> Config:
    required = [
        "TELEGRAM_LEAD_BOT_TOKEN",
        "TELEGRAM_MOD_BOT_TOKEN",
        "TELEGRAM_MOD_CHAT_ID",
        "ANTHROPIC_API_KEY",
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
        webhook_base_url=os.environ["WEBHOOK_BASE_URL"].rstrip("/"),
        database_path=os.getenv("DATABASE_PATH", "conversations.db"),
        port=int(os.getenv("PORT", "8000")),
    )
