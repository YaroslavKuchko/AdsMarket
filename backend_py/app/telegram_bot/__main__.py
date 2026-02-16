"""Run the Telegram bot for ad post flow. Usage: python -m app.telegram_bot"""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import MenuButtonWebApp, WebAppInfo

from app.core.config import settings
from app.telegram_bot.handlers import _get_webapp_url, router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    bot = Bot(token=settings.tg_bot_token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(router)
    try:
        # Set Menu Button to open Web App (next to message input)
        webapp_url = _get_webapp_url()
        await bot.set_chat_menu_button(menu_button=MenuButtonWebApp(text="Open", web_app=WebAppInfo(url=webapp_url)))
        logger.info("Menu button set to %s", webapp_url)
        logger.info("Bot polling started")
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
