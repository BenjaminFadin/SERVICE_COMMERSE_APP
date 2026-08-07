import logging
import sys

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from config import config
from database import init_db
from handlers import router


async def on_startup(bot: Bot):
    await init_db()
    await bot.set_webhook(
        url=config.webhook_url,
        secret_token=config.webhook_secret,
    )
    logging.getLogger(__name__).info(f"Webhook set → {config.webhook_url}")


async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logging.getLogger(__name__).info("Webhook deleted")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stdout,
    )

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
        
    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=config.webhook_secret,
    ).register(app, path=config.webhook_path)
    setup_application(app, dp, bot=bot)

    web.run_app(app, host=config.host, port=config.port)


if __name__ == "__main__":
    main()
