import asyncio
import os
import aiohttp
import logging
from datetime import datetime, timedelta
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Хранилище состояния пользователя
user_state = {}


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


def get_period_keyboard(city):
    """Кнопки выбора периода для города"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Сегодня", callback_data=f"period_today|{city}")
    builder.button(text="📅 Завтра", callback_data=f"period_tomorrow|{city}")
    builder.button(text="📅 7 дней", callback_data=f"period_week|{city}")
    builder.button(text="🔄 Изменить город", callback_data="change_city")
    builder.adjust(2, 2)
    return builder.as_markup()


@dp.message(CommandStart())
async def start_handler(message: Message):
    user_state[message.from_user.id] = {'city': None, 'last_period': None}
    await message.answer(
        "Привет! Я бот погоды 🌤️\n\n"
        "Напиши название города (например: Москва):"
    )


@dp.message(F.text)
async def handle_city(message: Message):
    city = message.text.strip()
    user_state[message.from_user.id] = {'city': city, 'last_period': None}
    
    await message.answer(
        f"✅ Город установлен: **{city}**\n\n"
        "Выбери период:",
        reply_markup=get_period_keyboard(city),
        parse_mode="Markdown"
    )


@dp.callback_query(F.data == "change_city")
async def change_city_handler(callback: CallbackQuery):
    user_state[callback.from_user.id] = {'city': None, 'last_period': None}
    await callback.message.edit_text(
        "Напиши название нового города:"
    )


@dp.callback_query(F.data.startswith("period_"))
async def period_handler(callback: CallbackQuery):
    await callback.answer()
    
    user_id = callback.from_user.id
    data = callback.data.split("|")
    period = data[0].replace("period_", "")
    city = data[1] if len(data) > 1 else user_state.get(user_id, {}).get('city', 'Москва')
    
    # Проверяем, не выбран ли уже этот период
    last_period = user_state.get(user_id, {}).get('last_period')
    if last_period == period:
        await callback.answer("Уже выбрано 👍", show_alert=True)
        return
    
    user_state[user_id] = {'city': city, 'last_period': period}
    
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?format=j1&lang=ru"
            async with session.get(url, timeout=10, headers={"User-Agent": "TelegramBot"}) as resp:
                if resp.status != 200:
                    await callback.message.edit_text("❌ Ошибка получения погоды.")
                    return
                data = await resp.json()
            
            if not data or 'weather' not in data:
                await callback.message.edit_text("❌ Город не найден.")
                return
            
            # Название города
            if data.get('nearest_area') and len(data['nearest_area']) > 0:
                area = data['nearest_area'][0]
                city_name = area.get('areaName', [{}])[0].get('value', city)
                country = area.get('country', [{}])[0].get('value', '')
                if country and country.lower() != 'russia':
                    city_name = f"{city_name}, {country}"
            else:
                city_name = city
            
            weather_list = data.get('weather', [])
            
            if period == "today" and len(weather_list) > 0:
                text = await format_day_weather(weather_list[0], city_name, "Сегодня")
            elif period == "tomorrow" and len(weather_list) > 1:
                text = await format_day_weather(weather_list[1], city_name, "Завтра")
            elif period == "week":
                text = await format_week_weather(weather_list[:7], city_name)
            else:
                text = await format_day_weather(weather_list[0], city_name, "Сегодня")
            
            try:
                await callback.message.edit_text(
                    text,
                    reply_markup=get_period_keyboard(city),
                    parse_mode="Markdown"
                )
            except Exception as edit_error:
                # Если контент не изменился, просто отвечаем в чат
                log.info(f"Edit failed, sending new message: {edit_error}")
                await callback.message.answer(
                    text,
                    reply_markup=get_period_keyboard(city),
                    parse_mode="Markdown"
                )
        
    except Exception as e:
        log.error(f"Error: {e}")
        await callback.message.edit_text(f"❌ Ошибка: {e}")


async def format_day_weather(forecast, city_name, day_label):
    """Форматирование погоды на один день"""
    hourly = forecast.get('hourly', [])
    
    if not hourly or len(hourly) == 0:
        return f"🌤 **Погода: {city_name}**\n📅 **{day_label}**\n\n❌ Нет данных"
    
    # Безопасное получение данных по времени суток
    def get_hour_data(index):
        if index < len(hourly):
            return hourly[index]
        # Если нет данных для индекса, берём ближайший
        return hourly[min(index, len(hourly) - 1)]
    
    morning = get_hour_data(6)
    day = get_hour_data(12)
    evening = get_hour_data(18)
    
    # Осадки по времени суток
    def get_precipitation(hour_data):
        chance_rain = int(hour_data.get('chanceofrain', 0))
        chance_snow = int(hour_data.get('chanceofsnow', 0))
        if chance_snow > 50:
            return f"❄️ {chance_snow}%"
        elif chance_rain > 50:
            return f"🌧️ {chance_rain}%"
        else:
            return "🌈 нет"
    
    morning_precip = get_precipitation(morning)
    day_precip = get_precipitation(day)
    evening_precip = get_precipitation(evening)
    
    text = f"🌤 **Погода: {city_name}**\n"
    text += f"📅 **{day_label}**\n\n"
    
    text += f"📈 Макс: {forecast.get('maxtempC', 0)}°C\n"
    text += f"📉 Мин: {forecast.get('mintempC', 0)}°C\n\n"
    
    text += f"**📅 Прогноз по времени:**\n"
    text += f"🌅 **Утро** (6:00): {morning.get('tempC', 0)}°C | Осадки: {morning_precip}\n"
    text += f"☀️ **День** (12:00): {day.get('tempC', 0)}°C | Осадки: {day_precip}\n"
    text += f"🌆 **Вечер** (18:00): {evening.get('tempC', 0)}°C | Осадки: {evening_precip}\n"
    
    # УФ-индекс (безопасное получение)
    uv_hour = get_hour_data(12)
    uv = int(uv_hour.get('uvIndex', 0))
    uv_text = "низкий" if uv <= 2 else "средний" if uv <= 5 else "высокий" if uv <= 7 else "очень высокий"
    text += f"\n☀️ УФ-индекс: {uv} ({uv_text})\n"
    
    return text


async def format_week_weather(weather_list, city_name):
    """Форматирование погоды на неделю"""
    days_ru = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    
    text = f"🌤 **Погода: {city_name}**\n"
    text += f"📅 **Прогноз на 7 дней**\n\n"
    
    today = datetime.now().weekday()
    
    for i, day in enumerate(weather_list):
        if i >= 7:
            break
        
        day_name = days_ru[(today + i) % 7]
        max_temp = day.get('maxtempC', 0)
        min_temp = day.get('mintempC', 0)
        
        # Иконка погоды
        hourly = day.get('hourly', [])
        weather_code = hourly[12].get('weatherCode', '116') if len(hourly) > 12 else '116'
        weather_icon = get_weather_icon(weather_code)
        
        # Осадки
        hour_data = hourly[12] if len(hourly) > 12 else (hourly[0] if hourly else {})
        chance_rain = int(hour_data.get('chanceofrain', 0))
        chance_snow = int(hour_data.get('chanceofsnow', 0))
        
        if chance_snow > 50:
            precip = f"❄️ {chance_snow}%"
        elif chance_rain > 50:
            precip = f"🌧️ {chance_rain}%"
        else:
            precip = "🌈"
        
        text += f"{weather_icon} **{day_name}**: {min_temp}°C...{max_temp}°C | {precip}\n"
    
    return text


def get_weather_icon(code):
    """Иконка погоды по коду"""
    code = str(code)
    if code in ['113']:
        return '☀️'
    elif code in ['116']:
        return '⛅'
    elif code in ['119', '122']:
        return '☁️'
    elif code in ['143', '248', '260']:
        return '🌫️'
    elif code in ['176', '263', '266', '293', '296', '353']:
        return '🌦️'
    elif code in ['179', '311', '314', '317', '350', '377']:
        return '🌨️'
    elif code in ['182', '185', '281', '284', '308', '311', '356', '359']:
        return '🌧️'
    elif code in ['200', '386', '389', '392', '395']:
        return '⛈️'
    elif code in ['227', '230', '320', '323', '326', '329', '332', '335', '338', '368', '371']:
        return '❄️'
    else:
        return '🌤️'


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


async def health_handler(request):
    return web.json_response({"status": "ok"})


if __name__ == "__main__":
    asyncio.run(main())
