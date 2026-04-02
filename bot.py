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
            # Используем wttr.in - бесплатный API без ключа
            url = f"https://wttr.in/{city}?format=j1&lang=ru"
            async with session.get(url, timeout=10, headers={"User-Agent": "TelegramBot"}) as resp:
                if resp.status != 200:
                    await message.answer("❌ Ошибка получения погоды. Попробуй позже.")
                    return
                data = await resp.json()
            
            if not data or 'current_condition' not in data or not data['current_condition']:
                await message.answer("❌ Город не найден. Попробуй ещё раз (например: Moscow):")
                return
            
            current = data['current_condition'][0]
            city_name = data['nearest_area'][0]['areaName'][0]['value'] if data.get('nearest_area') else city
            
            # Прогноз на сегодня
            forecast = data.get('weather', [{}])[0]
            
            text = f"🌤 **Погода: {city_name}**\n\n"
            text += f"📊 {current.get('weatherDesc', [{}])[0].get('value', 'Нет данных')}\n"
            text += f"🌡️ {current.get('temp_C', 0)}°C (ощущается {current.get('FeelsLikeC', 0)}°C)\n"
            text += f"💨 Ветер: {current.get('windspeedKmph', 0)} км/ч"
            if current.get('winddir16Point'):
                text += f" ({current['winddir16Point']})"
            text += "\n"
            text += f"💧 Влажность: {current.get('humidity', 0)}%\n"
            
            # Осадки
            chance_of_rain = forecast.get('hourly', [{}])[0].get('chanceofrain', '0')
            if int(chance_of_rain) > 50:
                text += f"🌧️ Вероятность осадков: {chance_of_rain}%\n"
            else:
                text += f"🌈 Осадков нет\n"
            
            # УФ-индекс
            uv_index = current.get('uvIndex', '0')
            text += f"\n☀️ УФ-индекс: {uv_index}"
            if int(uv_index) <= 2:
                text += " (низкий)"
            elif int(uv_index) <= 5:
                text += " (средний)"
            elif int(uv_index) <= 7:
                text += " (высокий)"
            else:
                text += " (очень высокий)"
            text += "\n"
            
            # Температура по времени суток
            hourly = forecast.get('hourly', [])
            if hourly:
                morning = hourly[6] if len(hourly) > 6 else hourly[0]
                day = hourly[12] if len(hourly) > 12 else hourly[0]
                evening = hourly[18] if len(hourly) > 18 else hourly[0]
                
                text += f"\n📅 **Прогноз на сегодня:**\n"
                text += f"🌅 Утро: {morning.get('temp_C', 0)}°C\n"
                text += f"☀️ День: {day.get('temp_C', 0)}°C\n"
                text += f"🌆 Вечер: {evening.get('temp_C', 0)}°C\n"
            
            text += f"\n_Будь здоров!_ 👋"
            
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
