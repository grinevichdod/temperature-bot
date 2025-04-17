# bot_barista.py

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv

from handlers import start, temperature
from scheduler import start_scheduler

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
        handlers=[
            logging.FileHandler("bot.log", encoding="utf-8"),
            logging.StreamHandler()
        ]
    )

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    # Регистрация роутеров
    dp.include_routers(
        start.router,
        temperature.router,
    )

    # Запуск планировщика
    start_scheduler(bot, dp)

    # Команды бота
    await bot.set_my_commands([
        BotCommand(command="start", description="Заполнить журнал температур")
    ])

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
