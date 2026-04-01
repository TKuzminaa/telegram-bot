import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден! Проверь переменные окружения.")

bot = Bot(token=TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_handler(message):
    await message.answer("Привет! Я бот.")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
