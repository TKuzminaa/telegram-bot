import asyncio
import os
import aiohttp
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import Message

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

TOKEN = os.getenv("BOT_TOKEN")
WEATHER_API = os.getenv("WEATHER_API", "")

if not TOKEN:
    raise RuntimeError("BOT_TOKEN не найден!")

if not WEATHER_API:
    log.warning("WEATHER_API не настроен!")

log.info(f"BOT_TOKEN: {'***' + TOKEN[-10:] if TOKEN else 'None'}")
log.info(f"WEATHER_API: {WEATHER_API[:8]}..." if WEATHER_API else "None")

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
            # Пробуем с https и правильным форматом
            url_geo = f"https://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={WEATHER_API}"
            log.info(f"Geo URL: {url_geo.replace(WEATHER_API, '***')}")
            
            async with session.get(url_geo, timeout=10, headers={"User-Agent": "TelegramBot"}) as resp:
                log.info(f"Geo status: {resp.status}")
                text = await resp.text()
                log.info(f"Geo response: {text[:500]}")
                
                if resp.status != 200:
                    await message.answer(f"❌ Ошибка API: {resp.status}. Проверь ключ WEATHER_API.")
                    return
                
                try:
                    geo_data = await resp.json()
                except:
                    await message.answer("❌ Ошибка формата ответа API.")
                    return
            
            if not geo_data or len(geo_data) == 0:
                await message.answer("❌ Город не найден. Попробуй ещё раз (например: Moscow):")
                return
            
            lat = geo_data[0]["lat"]
            lon = geo_data[0]["lon"]
            city_name = geo_data[0].get("name", city)
            
            # Погода
            url_weather = f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={WEATHER_API}&lang=ru&units=metric"
            log.info(f"Weather URL: {url_weather.replace(WEATHER_API, '***')}")
            
            async with session.get(url_weather, timeout=10, headers={"User-Agent": "TelegramBot"}) as resp:
                log.info(f"Weather status: {resp.status}")
                weather_data = await resp.json()
                log.info(f"Weather response: {weather_data}")
            
            if resp.status != 200:
                await message.answer(f"❌ Ошибка погоды: {weather_data.get('message', 'Unknown error')}")
                return
            
            main = weather_data.get("main", {})
            weather = weather_data.get("weather", [{}])[0]
            wind = weather_data.get("wind", {})
            
            text = f"🌤 **Погода: {city_name}**\n\n"
            text += f"📊 {weather.get('description', 'Нет данных').capitalize()}\n"
            text += f"🌡️ {main.get('temp', 0):.1f}°C (ощущается {main.get('feels_like', 0):.1f}°C)\n"
            text += f"💨 Ветер: {wind.get('speed', 0):.1f} м/с\n"
            text += f"💧 Влажность: {main.get('humidity', 0)}%\n"
            
            if 'rain' in weather_data:
                text += f"🌧️ Осадки: {weather_data['rain'].get('1h', 0)} мм\n"
            elif 'snow' in weather_data:
                text += f"❄️ Снег: {weather_data['snow'].get('1h', 0)} мм\n"
            else:
                text += f"🌈 Осадков нет\n"
            
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
