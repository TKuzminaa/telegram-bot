import asyncio
import os
import aiohttp
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден!")

bot = Bot(token=TOKEN)
dp = Dispatcher()


# Перевод описаний погоды
WEATHER_TRANSLATIONS = {
    'light rain': 'Небольшой дождь',
    'moderate rain': 'Дождь',
    'heavy rain': 'Сильный дождь',
    'light drizzle': 'Морось',
    'moderate drizzle': 'Морось',
    'heavy drizzle': 'Сильная морось',
    'light snow': 'Небольшой снег',
    'moderate snow': 'Снег',
    'heavy snow': 'Сильный снег',
    'light showers': 'Ливень',
    'moderate showers': 'Ливень',
    'heavy showers': 'Сильный ливень',
    'thunderstorm': 'Гроза',
    'thunderstorm with rain': 'Гроза с дождём',
    'thunderstorm with snow': 'Гроза со снегом',
    'thunderstorm with hail': 'Гроза с градом',
    'mist': 'Туман',
    'fog': 'Туман',
    'freezing fog': 'Ледяной туман',
    'partly cloudy': 'Переменная облачность',
    'cloudy': 'Облачно',
    'overcast': 'Пасмурно',
    'clear': 'Ясно',
    'sunny': 'Солнечно',
    'blowing snow': 'Позёмок',
    'blowing sand': 'Пыль',
    'haze': 'Дымка',
    'hazy': 'Дымка',
    'smoke': 'Дым',
    'dust': 'Пыль',
    'sand': 'Песок',
    'volcanic ash': 'Вулканический пепел',
    'squalls': 'Шквал',
    'tornado': 'Торнадо',
}

# Перевод направлений ветра
WIND_DIRECTIONS = {
    'N': 'С', 'NNE': 'ССВ', 'NE': 'СВ', 'ENE': 'ВСВ',
    'E': 'В', 'ESE': 'ЮВВ', 'SE': 'ЮВ', 'SSE': 'ЮЮВ',
    'S': 'Ю', 'SSW': 'ЮЮЗ', 'SW': 'ЮЗ', 'WSW': 'ЗЮЗ',
    'W': 'З', 'WNW': 'ЗСЗ', 'NW': 'СЗ', 'NNW': 'ССЗ',
}


def translate_weather(desc):
    """Перевод описания погоды на русский"""
    desc_lower = desc.lower()
    for key, value in WEATHER_TRANSLATIONS.items():
        if key in desc_lower:
            return value
    return desc.capitalize()


@dp.message(CommandStart())
async def start_handler(message: Message):
    log.info(f"Start from {message.from_user.id}")
    await message.answer(
        "Привет! Я бот погоды 🌤️\n\n"
        "Напиши название города (например: Москва):"
    )


@dp.message(F.text)
async def get_weather(message: Message):
    log.info(f"Got message: {message.text} from {message.from_user.id}")
    city = message.text.strip()
    
    try:
        async with aiohttp.ClientSession() as session:
            # wttr.in - бесплатный API без ключа
            url = f"https://wttr.in/{city}?format=j1&lang=ru"
            async with session.get(url, timeout=10, headers={"User-Agent": "TelegramBot"}) as resp:
                if resp.status != 200:
                    await message.answer("❌ Ошибка получения погоды. Попробуй позже.")
                    return
                data = await resp.json()
            
            if not data or 'current_condition' not in data or not data['current_condition']:
                await message.answer("❌ Город не найден. Попробуй ещё раз (например: Москва):")
                return
            
            current = data['current_condition'][0]
            
            # Название города
            if data.get('nearest_area') and len(data['nearest_area']) > 0:
                area = data['nearest_area'][0]
                city_name = area.get('areaName', [{}])[0].get('value', city)
                country = area.get('country', [{}])[0].get('value', '')
                if country and country.lower() != 'russia':
                    city_name = f"{city_name}, {country}"
            else:
                city_name = city
            
            # Прогноз на сегодня
            forecast = data.get('weather', [{}])[0]
            
            # Описание погоды
            weather_desc = current.get('weatherDesc', [{}])[0].get('value', 'Нет данных')
            weather_ru = translate_weather(weather_desc)
            
            text = f"🌤 **Погода: {city_name}**\n\n"
            text += f"📊 {weather_ru}\n"
            text += f"🌡️ {current.get('temp_C', 0)}°C (ощущается {current.get('FeelsLikeC', 0)}°C)\n"
            
            # Ветер
            wind_speed = current.get('windspeedKmph', 0)
            wind_dir = current.get('winddir16Point', '')
            wind_dir_ru = WIND_DIRECTIONS.get(wind_dir, wind_dir) if wind_dir else ''
            
            text += f"💨 Ветер: {wind_speed} км/ч"
            if wind_dir_ru:
                text += f" ({wind_dir_ru})"
            text += "\n"
            
            text += f"💧 Влажность: {current.get('humidity', 0)}%\n"
            
            # Видимость
            visibility = current.get('visibility', 0)
            if visibility:
                text += f"👁️ Видимость: {visibility} км\n"
            
            # Давление
            pressure = current.get('pressure', 0)
            if pressure:
                text += f"🔽 Давление: {pressure} гПа\n"
            
            # Осадки
            chance_of_rain = forecast.get('hourly', [{}])[0].get('chanceofrain', '0')
            chance_of_snow = forecast.get('hourly', [{}])[0].get('chanceofsnow', '0')
            
            if int(chance_of_rain) > 50:
                text += f"🌧️ Вероятность дождя: {chance_of_rain}%\n"
            elif int(chance_of_snow) > 50:
                text += f"❄️ Вероятность снега: {chance_of_snow}%\n"
            else:
                text += f"🌈 Осадков не ожидается\n"
            
            # УФ-индекс
            uv_index = current.get('uvIndex', 0)
            text += f"\n☀️ УФ-индекс: {uv_index}"
            uv = int(uv_index) if uv_index else 0
            if uv <= 2:
                text += " (низкий) ☑️"
            elif uv <= 5:
                text += " (средний) ⚠️"
            elif uv <= 7:
                text += " (высокий) 🛡️"
            else:
                text += " (очень высокий) 🚫"
            text += "\n"
            
            # Температура по времени суток
            hourly = forecast.get('hourly', [])
            if hourly and len(hourly) >= 3:
                # Индексы для утра (6), дня (12), вечера (18)
                morning_idx = min(6, len(hourly) - 1)
                day_idx = min(12, len(hourly) - 1)
                evening_idx = min(18, len(hourly) - 1)
                
                morning = hourly[morning_idx]
                day = hourly[day_idx]
                evening = hourly[evening_idx]
                
                text += f"\n📅 **Прогноз на сегодня:**\n"
                text += f"🌅 Утро (6:00): {morning.get('tempC', 0)}°C\n"
                text += f"☀️ День (12:00): {day.get('tempC', 0)}°C\n"
                text += f"🌆 Вечер (18:00): {evening.get('tempC', 0)}°C\n"
            
            # Мин/макс температура
            max_temp = forecast.get('maxtempC', 0)
            min_temp = forecast.get('mintempC', 0)
            if max_temp or min_temp:
                text += f"\n📈 Макс: {max_temp}°C  📉 Мин: {min_temp}°C\n"
            
            text += f"\n_Хорошего дня!_ 👋"
            
            await message.answer(text, parse_mode="Markdown")
        
    except Exception as e:
        log.error(f"Error: {e}")
        await message.answer(f"❌ Ошибка: {e}")


async def health_handler(request):
    return web.json_response({"status": "ok"})


async def main():
    log.info("Bot starting...")
    polling_task = asyncio.create_task(dp.start_polling(bot))
    
    app = web.Application()
    app.router.add_get('/health', health_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    log.info("Health server started on port 8080")
    
    await polling_task


if __name__ == "__main__":
    asyncio.run(main())
