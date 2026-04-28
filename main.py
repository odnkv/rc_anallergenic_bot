import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from bot.handlers import router
from bot.scheduler import start_scheduler, stop_scheduler, run_price_update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Config from environment ────────────────────────────────────────────────────

BOT_TOKEN = os.environ["BOT_TOKEN"]
WEBHOOK_HOST = os.environ.get("RAILWAY_STATIC_URL") or os.environ.get("WEBHOOK_HOST", "")
WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"https://{WEBHOOK_HOST}{WEBHOOK_PATH}"
WEB_PORT = int(os.environ.get("PORT", 8080))


# ── Lifecycle ──────────────────────────────────────────────────────────────────

async def on_startup(bot: Bot):
    logger.info(f"Setting webhook: {WEBHOOK_URL}")
    await bot.set_webhook(WEBHOOK_URL)
    start_scheduler(bot)
    # Run first price fetch immediately on startup
    asyncio.create_task(run_price_update(bot=bot))
    logger.info("Bot started.")


async def on_shutdown(bot: Bot):
    stop_scheduler()
    await bot.delete_webhook()
    logger.info("Bot stopped.")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()
    dp.include_router(router)
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    logger.info(f"Starting web server on port {WEB_PORT}")
    web.run_app(app, host="0.0.0.0", port=WEB_PORT)


if __name__ == "__main__":
    main()
