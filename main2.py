import os
import time
import re
import logging
import requests
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
HF_TOKEN = os.getenv("HF_TOKEN")
PAYMENT_LINK = os.getenv("PAYMENT_LINK", "https://example.com")
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST")  # e.g. https://your-bot.onrender.com
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}" if WEBHOOK_HOST else ""

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Стили
STYLES = {
    "конфетти": "candy",
    "мозаика": "mosaic",
    "принцесса дождя": "rain_princess",
    "удни": "udnie"
}

# Хранилища
user_style = {}                # кто выбрал стиль
paid_users = {}                # {user_id: timestamp_окончания}
pending_payments = {}          # {user_id: file_id_скрина}

# Вспомогательные функции
def is_paid(user_id: int) -> bool:
    if user_id in paid_users:
        if time.time() < paid_users[user_id]:
            return True
        else:
            del paid_users[user_id]
    return False

def grant_access(user_id: int, hours: int = 24):
    paid_users[user_id] = time.time() + hours * 3600

async def process_image(message: Message):
    user_id = message.from_user.id
    style_key = user_style.get(user_id)
    if not style_key:
        await message.answer("Сначала выбери стиль: " + ", ".join(STYLES.keys()))
        return

    await message.answer("⏳ Обрабатываю... (5–10 сек)")

    photo = message.photo[-1]
    try:
        file = await bot.get_file(photo.file_id)
        file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file.file_path}"
    except Exception as e:
        logging.error(f"Ошибка получения файла: {e}")
        await message.answer("Не удалось загрузить фото. Попробуй снова.")
        return

    try:
        API_URL = f"https://api-inference.huggingface.co/models/akhooli/fast-style-transfer/{style_key}"
        headers = {"Authorization": f"Bearer {HF_TOKEN}"}
        response = requests.post(API_URL, headers=headers, json={"inputs": file_url}, timeout=60)

        if response.status_code == 200:
            await message.answer_photo(photo=response.content, caption="✨ Вот твой арт!")
        else:
            error = response.json().get("error", "Неизвестная ошибка API")
            await message.answer(f"❌ Ошибка обработки: {error}")
            logging.error(f"HF API error: {response.text}")
    except Exception as e:
        await message.answer("Ошибка при генерации. Попробуй позже.")
        logging.error(f"Exception in process_image: {e}")

# Команды
@dp.message(Command("start"))
async def start(message: Message):
    styles_list = ", ".join(STYLES.keys())
    await message.answer(
        "🎨 Привет! Я — бот-художник.\n"
        f"Стили: {styles_list}\n\n"
        "1. Напиши название стиля\n"
        "2. Отправь фото\n\n"
        "Первая обработка — бесплатно! ❤️"
    )

@dp.message(Command("pay"))
async def cmd_pay(message: Message):
    await message.answer(
        "Поддержи бота — 99 ₽ за 24 часа неограниченного доступа!\n"
        f"🔗 Оплатить: {PAYMENT_LINK}\n\n"
        "После оплаты пришли **скриншот подтверждения перевода** (должно быть видно сумму и получателя)."
    )

# Обработка текста (выбор стиля)
@dp.message(lambda msg: msg.text and not msg.photo)
async def handle_text(message: Message):
    text = message.text.strip().lower()
    for name, key in STYLES.items():
        if text == name.lower():
            user_style[message.from_user.id] = key
            await message.answer(f"Отлично! Теперь пришли фото для стиля «{name}».")
            return
    await message.answer("Неизвестный стиль. Доступные: " + ", ".join(STYLES.keys()))

# Обработка фото
@dp.message(lambda msg: msg.photo)
async def handle_photo(message: Message):
    user_id = message.from_user.id

    if is_paid(user_id):
        await process_image(message)
        return

    # Бесплатная попытка — только если стиль выбран
    if user_id in user_style:
        await process_image(message)
        # После первой генерации — предложить оплату
        await message.answer(
            "✨ Первая картинка — в подарок!\n"
            "Хочешь больше? Поддержи бота — 99 ₽ за 24 часа неограниченного доступа!\n"
            f"🔗 /pay"
        )
        # Удаляем стиль, чтобы не спамил
        user_style.pop(user_id, None)
    else:
        await message.answer("Сначала напиши стиль: " + ", ".join(STYLES.keys()))

# Приём скриншотов оплаты
@dp.message(lambda msg: msg.photo and not is_paid(msg.from_user.id) and msg.caption and "скрин" in msg.caption.lower())
async def fallback_payment_handler(message: Message):
    await handle_payment_proof(message)

@dp.message(lambda msg: msg.photo and not is_paid(msg.from_user.id))
async def handle_payment_proof(message: Message):
    user_id = message.from_user.id
    pending_payments[user_id] = message.photo[-1].file_id
    await message.answer("✅ Скриншот получен! Ожидай подтверждения (обычно в течение часа).")

    if ADMIN_ID:
        try:
            await bot.send_photo(
                ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=f"Новый платёж!\nID: {user_id}\nUsername: @{message.from_user.username or 'нет'}\n\n"
                        f"Чтобы подтвердить, отправь: /approve_{user_id}"
            )
        except Exception as e:
            logging.error(f"Не удалось отправить админу: {e}")

# Подтверждение от админа
@dp.message(lambda msg: str(msg.from_user.id) == str(ADMIN_ID) and msg.text)
async def admin_approve(message: Message):
    text = message.text.strip()
    match = re.match(r"/approve_(\d+)", text)
    if match:
        user_id = int(match.group(1))
        grant_access(user_id, hours=24)
        try:
            await bot.send_message(user_id, "✅ Оплата подтверждена! У тебя 24 часа неограниченного доступа. Твори!")
        except:
            pass
        await message.answer(f"✅ Доступ выдан пользователю {user_id}")

# Webhook setup
async def on_startup(app):
    if WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL, drop_pending_updates=True)
        logging.info(f"Webhook установлен: {WEBHOOK_URL}")
    else:
        logging.warning("WEBHOOK_HOST не задан — бот работает в polling (не для Render!)")

async def on_shutdown(app):
    await bot.delete_webhook()
    await bot.session.close()

# Запуск
if __name__ == "__main__":
    app = web.Application()
    webhook_handler = SimpleRequestHandler(dispatcher=dp, bot=bot)
    webhook_handler.register(app, path=WEBHOOK_PATH)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.getenv("PORT", 8000))
    web.run_app(app, host="0.0.0.0", port=port)
