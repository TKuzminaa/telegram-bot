import asyncio
import os
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Токен бота
TOKEN = os.getenv("BOT_TOKEN")
# API ключ OpenWeatherMap (бесплатный)
WEATHER_API = os.getenv("WEATHER_API", "7d6e6f8a5c3b2e1f9d8c7a6b5e4d3c2f")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден! Проверь переменные окружения.")

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
        # Поиск города
        url_geo = f"http://api.openweathermap.org/geo/1.0?q={city},RU&limit=1&appid={WEATHER_API}&lang=ru"
        async with session.get(url_geo) as resp:
            geo_data = await resp.json()
        
        if not geo_data:
            await message.answer(
                f"❌ Город '{city}' не найден.\n\n"
                "Попробуй написать название ещё раз (например: Москва):"
            )
            return
        
        lat = geo_data[0]["lat"]
        lon = geo_data[0]["lon"]
        city_name = geo_data[0]["name"]
        
        # Получаем погоду
        url_weather = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API}&lang=ru&units=metric"
        async with session.get(url_weather) as resp:
            weather_data = await resp.json()
        
        # Получаем прогноз на день
        url_forecast = f"https://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={WEATHER_API}&lang=ru&units=metric"
        async with session.get(url_forecast) as resp:
            forecast_data = await resp.json()
    
    # Парсим данные
    main = weather_data["main"]
    weather = weather_data["weather"][0]
    wind = weather_data["wind"]
    
    # Прогноз по времени суток (группируем по 3 часа)
    forecast = forecast_data["list"][:8]  # ближайшие 24 часа
    
    temp_morning = []
    temp_day = []
    temp_evening = []
    
    for item in forecast:
        hour = int(item["dt_txt"].split(" ")[1].split(":")[0])
        temp = item["main"]["temp"]
        if 6 <= hour < 12:
            temp_morning.append(temp)
        elif 12 <= hour < 18:
            temp_day.append(temp)
        elif 18 <= hour < 24:
            temp_evening.append(temp)
    
    # Формируем ответ
    weather_text = f"🌤 **Погода в городе {city_name}**\n\n"
    weather_text += f"📊 **Сейчас:** {weather['description'].capitalize()}\n"
    weather_text += f"🌡️ **Температура:** {main['temp']}°C (ощущается как {main['feels_like']}°C)\n"
    
    weather_text += f"\n📅 **Прогноз на сегодня:**\n"
    if temp_morning:
        weather_text += f"🌅 **Утро:** {sum(temp_morning)/len(temp_morning):.1f}°C\n"
    if temp_day:
        weather_text += f"☀️ **День:** {sum(temp_day)/len(temp_day):.1f}°C\n"
    if temp_evening:
        weather_text += f"🌆 **Вечер:** {sum(temp_evening)/len(temp_evening):.1f}°C\n"
    
    weather_text += f"\n💨 **Ветер:** {wind.get('speed', 0):.1f} м/с"
    if 'deg' in wind:
        directions = {0: 'С', 45: 'СВ', 90: 'В', 135: 'ЮВ', 180: 'Ю', 225: 'ЮЗ', 270: 'З', 315: 'СЗ'}
        deg = wind['deg']
        closest = min(directions.keys(), key=lambda x: abs(x - deg))
        weather_text += f" ({directions[closest]})"
    weather_text += "\n"
    
    weather_text += f"💧 **Влажность:** {main['humidity']}%\n"
    weather_text += f"🌡️ **Давление:** {main.get('pressure', 0)} гПа\n"
    
    # Осадки
    if 'rain' in weather_data:
        rain = weather_data['rain'].get('1h', 0)
        weather_text += f"🌧️ **Осадки:** {rain} мм/час\n"
    elif 'snow' in weather_data:
        snow = weather_data['snow'].get('1h', 0)
        weather_text += f"❄️ **Снег:** {snow} мм/час\n"
    else:
        weather_text += f"🌈 **Осадки:** нет\n"
    
    # УФ-индекс (в бесплатном API нет, пишем заглушку)
    weather_text += f"\n☀️ **УФ-индекс:** данные недоступны в бесплатном API\n"
    weather_text += f"(летом днём обычно 3-7, зимой 0-2)\n"
    
    weather_text += f"\n_Будь здоров!_ 👋"
    
    await message.answer(weather_text, parse_mode="Markdown")
    await state.clear()


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
