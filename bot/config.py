import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    website_url: str
    db_url: str


def load_config() -> Config:
    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME")

    db_url = f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    return Config(
        bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        website_url=os.getenv("WEBSITE_URL", "https://example.com"),
        db_url=db_url,
    )

config = load_config()

