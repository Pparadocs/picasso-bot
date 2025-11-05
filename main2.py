import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.types import Message
from aiogram.filters import Command
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Стили (для примера)
STYLES = {
    "конфетти": "candy",
    "мозаика": "mosaic",
    "принцесса дождя": "rain_princess",
    "удни": "udnie"
}

# Хранилища
user_style = {}  # {user_id: style_key}

# Вспомогательные функции
async def process_image(message: Message):
    user_id = message.from_user.id
    style_key = user_style.get(user_id)
    if not style_key:
        await bot.send_message(user_id, "Сначала выбери стиль: " + ", ".join(STYLES.keys()))
        return

    await bot.send_message(user_id, "⏳ Обрабатываю... (5–10 сек)")

    photo = message.photo[-1]
    try:
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    except Exception as e:
        logging.error(f"Ошибка получения файла: {e}")
        await bot.send_message(user_id, "Не удалось загрузить фото. Попробуй снова.")
        return

    try:
        import requests
        API_URL = f"https://api-inference.huggingface.co/models/akhooli/fast-style-transfer/{style_key}"
        headers = {"Authorization": f"Bearer {os.getenv('HF_TOKEN')}"}
        response = requests.post(API_URL, headers=headers, json={"inputs": file_url}, timeout=60)

        if response.status_code == 200:
            await bot.send_photo(user_id, photo=response.content, caption="✨ Вот твой арт!")
        else:
            error = response.json().get("error", "Неизвестная ошибка API")
            await bot.send_message(user_id, f"❌ Ошибка обработки: {error}")
            logging.error(f"HF API error: {response.text}")
    except Exception as e:
        await bot.send_message(user_id, "Ошибка при генерации. Попробуй позже.")
        logging.error(f"Exception in process_image: {e}")

# Команды
@dp.message(Command("start"))
async def start(message: Message):
    styles_list = ", ".join(STYLES.keys())
    await bot.send_message(
        message.from_user.id,
        "🎨 Привет! Я — бот-художник.\n"
        f"Стили: {styles_list}\n\n"
        "1. Напиши название стиля\n"
        "2. Отправь фото\n\n"
        "У тебя **2 бесплатных использования** — потом /pay"
    )

@dp.message(Command("setwebhook"))
async def set_webhook_command(message: Message):
    webhook_url = f"https://picasso-bot-nilp.onrender.com/webhook"
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    await message.answer(f"✅ Вебхук установлен: {webhook_url}")

# Обработка текста (выбор стиля)
@dp.message(lambda msg: msg.text and not msg.photo)
async def handle_text(message: Message):
    text = message.text.strip().lower()
    for name, key in STYLES.items():
        if text == name.lower():
            user_style[message.from_user.id] = key
            await bot.send_message(message.from_user.id, f"Отлично! Теперь пришли фото для стиля «{name}».")
            return
    await bot.send_message(message.from_user.id, "Неизвестный стиль. Доступные: " + ", ".join(STYLES.keys()))

# Обработка фото
@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message):
    await process_image(message)

# aiohttp routes
async def handle_webhook(request: web.Request):
    try:
        json_string = await request.text()
        update = Update.model_validate_json(json_string)
        await dp.feed_update(bot, update)
        return web.json_response({"ok": True})
    except Exception as e:
        logging.error(f"Ошибка вебхука: {e}")
        return web.json_response({"ok": False}, status=500)

async def handle_index(request: web.Request):
    return web.Response(text="Bot is running", status=200)

# Запуск
if __name__ == "__main__":
    app = web.Application()
    app.add_routes([
        web.post('/webhook', handle_webhook),
        web.get('/', handle_index),
    ])
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)
