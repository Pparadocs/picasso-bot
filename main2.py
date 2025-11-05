import os
import logging
from io import BytesIO
from aiogram import Bot, Dispatcher
from aiogram.types import Update, Message
from aiogram.filters import Command
from aiohttp import web
from PIL import Image, ImageOps

# Логирование
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

STYLES = {
    "инверсия": lambda img: ImageOps.invert(img.convert("RGB")),
    "ч/б": lambda img: img.convert("L").convert("RGB"),
    "зеркало": lambda img: ImageOps.mirror(img),
    "поворот": lambda img: img.rotate(90, expand=True),
}

user_style = {}

async def process_image(message: Message):
    user_id = message.from_user.id
    func = user_style.get(user_id)
    if not func:
        await bot.send_message(user_id, "Сначала выбери стиль: " + ", ".join(STYLES.keys()))
        return

    photo = message.photo[-1]
    try:
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        import requests
        resp = requests.get(file_url)
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        result = func(img)

        output = BytesIO()
        result.save(output, format="JPEG")
        output.seek(0)
        await bot.send_photo(user_id, photo=output, caption="✨ Готово!")
    except Exception as e:
        await bot.send_message(user_id, "Ошибка. Попробуй другое фото.")
        logging.error(e)

@dp.message(Command("start"))
async def start(message: Message):
    await bot.send_message(
        message.from_user.id,
        "🎨 Бот-редактор (бесплатно):\n" + ", ".join(STYLES.keys()) + "\n\n1. Напиши стиль\n2. Отправь фото"
    )

@dp.message(lambda m: m.text and not m.photo)
async def choose_style(message: Message):
    text = message.text.strip().lower()
    for name, fn in STYLES.items():
        if text == name.lower():
            user_style[message.from_user.id] = fn
            await bot.send_message(message.from_user.id, f"Отлично! Пришли фото для стиля «{name}».")
            return
    await bot.send_message(message.from_user.id, "Неизвестный стиль. Выбери: " + ", ".join(STYLES.keys()))

@dp.message(lambda m: m.photo)
async def handle_photo(message: Message):
    await process_image(message)

# Webhook
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
    logging.info("Webhook установлен")

app = web.Application()
app.add_routes([web.post('/webhook', handle_webhook), web.get('/', lambda r: web.Response(text="OK"))])
app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    web.run_app(app, host="0.0.0.0", port=port)
