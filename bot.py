import asyncio
import os
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()


class WeatherState(StatesGroup):
    city = State()


@dp.message(CommandStart())
async def start_handler(message: Message, state: FSMContext):
    await state.set_state(WeatherState.city)
    await message.answer(
        "Привет! Я бот погоды 🌤️\n\n"
        "Напиши название города (например: Москва, Санкт-Петербург, Казань):"
    )


@dp.message(WeatherState.city)
async def get_weather(message: Message, state: FSMContext):
    city = message.text.strip()
    
    async with aiohttp.ClientSession() as session:
        url_geo = f"http://api.openweathermap.org/geo/1.0?q={city},RU&limit=1&appid=7d6e6f8a5c3b2e1f9d8c7a6b5e4d3c2f&lang=ru"
        async with session.get(url_geo) as resp:
            geo_data = await resp.json()
        
        if not geo_data:
            await message.answer("❌ Город не найден. Попробуй ещё раз:")
            return
        
        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]
        city_name = geo_data[0]["name"]
        
        url_weather = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid=7d6e6f8a5c3b2e1f9d8c7a6b5e4d3c2f&lang=ru&units=metric"
        async with session.get(url_weather) as resp:
            weather_data = await resp.json()
    
    main = weather_data["main"]
    weather = weather_data["weather"][0]
    wind = weather_data["wind"]
    
    text = f"🌤 **Погода: {city_name}**\n\n"
    text += f"📊 {weather['description'].capitalize()}\n"
    text += f"🌡️ {main['temp']}°C (ощущается {main['feels_like']}°C)\n"
    text += f"💨 Ветер: {wind.get('speed', 0):.1f} м/с\n"
    text += f"💧 Влажность: {main['humidity']}%\n"
    
    if 'rain' in weather_data:
        text += f"🌧️ Осадки: {weather_data['rain'].get('1h', 0)} мм\n"
    else:
        text += f"🌈 Осадков нет\n"
    
    await message.answer(text, parse_mode="Markdown")
    await state.clear()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
