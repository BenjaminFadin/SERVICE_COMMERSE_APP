import os
import secrets
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    website_url: str
    db_url: str
    # Webhook settings
    webhook_url: str    # e.g. https://ibron.uz/bot/webhook
    webhook_path: str   # e.g. /bot/webhook
    webhook_secret: str # random token for request validation
    host: str           # local bind address for the bot's aiohttp server
    port: int           # local port for the bot's aiohttp server


def load_config() -> Config:
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")

    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set in .env file")

    domain = os.getenv("DOMAIN_NAME", "ibron.uz").rstrip("/")
    webhook_path = os.getenv("BOT_WEBHOOK_PATH", "/bot/webhook")

    return Config(
        bot_token=bot_token,
        website_url=os.getenv("WEBSITE_URL", f"https://{domain}/"),
        db_url=db_url,
        webhook_url=f"https://{domain}{webhook_path}",
        webhook_path=webhook_path,
        webhook_secret=os.getenv("BOT_WEBHOOK_SECRET", secrets.token_hex(32)),
        host=os.getenv("BOT_HOST", "127.0.0.1"),
        port=int(os.getenv("BOT_PORT", "8080")),
    )


config = load_config()
