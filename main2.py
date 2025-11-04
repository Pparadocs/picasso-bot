import os
import logging
from io import BytesIO
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.types import Message
from aiogram.filters import Command
from aiohttp import web
from PIL import Image, ImageFilter, ImageOps, ImageEnhance

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Стили (функции обработки)
STYLES = {
    "размытие": lambda img: img.filter(ImageFilter.GaussianBlur(radius=5)),
    "контур": lambda img: img.filter(ImageFilter.CONTOUR),
    "инверт": lambda img: ImageOps.invert(img.convert("RGB")),
    "яркость": lambda img: ImageEnhance.Brightness(img).enhance(1.5),
    "резкость": lambda img: ImageEnhance.Sharpness(img).enhance(2.0),
    "пиксель-арт": lambda img: img.resize((img.width // 10, img.height // 10), resample=Image.NEAREST).resize((img.width * 10, img.height * 10), resample=Image.NEAREST),
    "черно-белое": lambda img: img.convert("L").convert("RGB"),
    "тиснение": lambda img: img.filter(ImageFilter.EMBOSS),
    "тиснение-2": lambda img: img.filter(ImageFilter.FIND_EDGES),
}

# Хранилища
user_style = {}  # {user_id: function}

# Вспомогательные функции
async def process_image(message: Message):
    user_id = message.from_user.id
    style_func = user_style.get(user_id)
    if not style_func:
        await bot.send_message(user_id, "Сначала выбери стиль: " + ", ".join(STYLES.keys()))
        return

    await bot.send_message(user_id, "⏳ Обрабатываю...")

    photo = message.photo[-1]
    try:
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
        response = requests.get(file_url)
        image_bytes = response.content
    except Exception as e:
        logging.error(f"Ошибка получения файла: {e}")
        await bot.send_message(user_id, "Не удалось загрузить фото. Попробуй снова.")
        return

    try:
        # ✅ Открываем фото
        image = Image.open(BytesIO(image_bytes)).convert("RGB")

        # ✅ Применяем стиль
        result_image = style_func(image)

        # ✅ Отправляем фото
        with BytesIO() as output:
            result_image.save(output, format="JPEG")
            output.seek(0)
            await bot.send_photo(user_id, photo=output, caption="✨ Вот твой арт!")
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
        "Бот бесплатный, без ограничений!"
    )

# Обработка текста (выбор стиля)
@dp.message(lambda msg: msg.text and not msg.photo)
async def handle_text(message: Message):
    text = message.text.strip().lower()
    for name, func in STYLES.items():
        if text == name.lower():
            user_style[message.from_user.id] = func
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

# Webhook setup
async def on_startup(app):
    webhook_url = f"https://picasso-bot-nilp.onrender.com/webhook"  # ⬅️ твой URL
    await bot.set_webhook(webhook_url, drop_pending_updates=True)
    logging.info(f"Webhook установлен: {webhook_url}")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

# Запуск
if __name__ == "__main__":
    import requests  # Нужен для скачивания фото
    app = web.Application()
    app.add_routes([
        web.post('/webhook', handle_webhook),
        web.get('/', handle_index),
    ])
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.getenv("PORT", 8000))
    web.run_app(app, host="0.0.0.0", port=port)
