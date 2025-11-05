import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message
from aiogram.filters import Command
from aiohttp import web

logging.basicConfig(level=logging.INFO)
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: Message):
    await bot.send_message(message.from_user.id, "✅ Бот работает!")

async def handle_webhook(request: web.Request):
    try:
        json_str = await request.text()
        update = Update.model_validate_json(json_str)
        await dp.feed_update(bot, update)
        return web.json_response({"ok": True})
    except Exception as e:
        logging.error(e)
        return web.json_response({"ok": False}, status=500)

async def on_startup(app):
    url = f"https://picasso-bot-nilp.onrender.com/webhook"
    await bot.set_webhook(url)
    logging.info("✅ Вебхук установлен")

app = web.Application()
app.add_routes([web.post('/webhook', handle_webhook)])
app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)
