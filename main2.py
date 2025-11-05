import os
import logging
import requests
from io import BytesIO
from PIL import Image, ImageFilter, ImageOps, ImageEnhance, ImageDraw, ImageFont
from flask import Flask, request
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# --- Настройки ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
if not TELEGRAM_TOKEN:
    raise ValueError("Необходимо установить переменную окружения TELEGRAM_TOKEN")

APP_URL = os.environ.get('APP_URL')
if not APP_URL:
    raise ValueError("Необходимо установить переменную окружения APP_URL")

# --- Логирование ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Инициализация Flask ---
app = Flask(__name__)

# --- Инициализация Telegram Application ---
application = Application.builder().token(TELEGRAM_TOKEN).build()

# --- Словарь для хранения выбранного стиля пользователем (в реальных условиях используйте БД) ---
user_styles = {}

# --- Словарь стилей ---
STYLES = {
    "pixel": "Pixel Art",
    "anime": "Anime",
    "vangogh": "Van Gogh",
    "blur": "Blur",
    "edge": "Edge Enhance",
    "contour": "Contour",
    "emboss": "Emboss"
}

# --- Функция для применения стиля ---
def apply_style(image_bytes, style):
    try:
        image = Image.open(BytesIO(image_bytes))

        # --- Примеры стилей ---
        if style == "pixel":
            # Уменьшаем размер, затем увеличиваем, чтобы получить пиксельный эффект
            small = image.resize((image.width // 8, image.height // 8), Image.NEAREST) # Уменьшаем в 8 раз
            processed_image = small.resize(image.size, Image.NEAREST) # Увеличиваем обратно
        elif style == "anime":
            # Простой эффект "аниме": повышение резкости и контраста
            processed_image = image.filter(ImageFilter.SHARPEN)
            enhancer = ImageEnhance.Contrast(processed_image)
            processed_image = enhancer.enhance(1.2) # Увеличиваем контраст
        elif style == "vangogh":
            # Простой эффект "Ван Гога": сильное размытие и усиление краев
            # Используем фильтры для имитации мазка кисти
            blur_img = image.filter(ImageFilter.GaussianBlur(radius=1))
            edge_img = blur_img.filter(ImageFilter.EDGE_ENHANCE_MORE)
            # Пытаемся наложить края на размытое изображение (упрощенно)
            processed_image = Image.blend(blur_img, edge_img, alpha=0.3)
        elif style == "blur":
            processed_image = image.filter(ImageFilter.GaussianBlur(radius=2))
        elif style == "edge":
            processed_image = image.filter(ImageFilter.EDGE_ENHANCE)
        elif style == "contour":
            processed_image = image.filter(ImageFilter.CONTOUR)
        elif style == "emboss":
            processed_image = image.filter(ImageFilter.EMBOSS)
        else:
            # Если стиль неизвестен, возвращаем оригинальное изображение
            processed_image = image

        # Сохраняем в BytesIO для отправки
        output_buffer = BytesIO()
        processed_image.save(output_buffer, format='JPEG', quality=90) # Установим качество, чтобы уменьшить размер
        output_buffer.seek(0)
        return output_buffer
    except Exception as e:
        logger.error(f"Ошибка применения стиля '{style}': {e}")
        return None

# --- Асинхронная функция для обработки выбора стиля (Callback Query) ---
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # Отвечаем на callback, чтобы убрать "часики"

    user_id = query.from_user.id
    style_choice = query.data

    if style_choice in STYLES:
        user_styles[user_id] = style_choice
        await query.edit_message_text(text=f"Стиль '{STYLES[style_choice]}' выбран! Теперь отправьте изображение для обработки.")
    else:
        await query.edit_message_text(text="Произошла ошибка. Пожалуйста, начните снова.")

# --- Асинхронная функция для обработки сообщений ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    message = update.effective_message

    logger.info(f"Получено сообщение от {user_id}: {message.text or 'Фото/Документ'}")

    # --- Отвечаем на любое текстовое сообщение ---
    if message.text:
        if message.text == "/start":
             # Создаем inline-клавиатуру с выбором стиля
            keyboard = [[InlineKeyboardButton(name, callback_data=style)] for style in STYLES.keys()]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text("Привет! Выберите стиль обработки изображения:", reply_markup=reply_markup)
        else:
            await message.reply_text("Привет! Отправьте команду /start, чтобы выбрать стиль, а затем пришлите изображение.")

    # --- Обработка изображений ---
    photo = message.photo
    document = message.document

    image_bytes = None
    if photo:
        file_id = photo[-1].file_id
        new_file = await context.bot.get_file(file_id)
        image_bytes = BytesIO()
        await new_file.download_to_memory(image_bytes)
    elif document and document.mime_type and document.mime_type.startswith('image/'):
        new_file = await context.bot.get_file(document.file_id)
        image_bytes = BytesIO()
        await new_file.download_to_memory(image_bytes)

    if image_bytes:
        # Проверяем, выбрал ли пользователь стиль
        selected_style = user_styles.get(user_id)
        if not selected_style:
            await message.reply_text("Сначала выберите стиль обработки с помощью команды /start.")
            return

        logger.info(f"Начинаю обработку изображения пользователя {user_id} в стиле '{selected_style}'...")
        processed_image_buffer = apply_style(image_bytes.getvalue(), selected_style)
        if processed_image_buffer:
            await message.reply_photo(photo=processed_image_buffer, caption=f"Ваше изображение в стиле '{STYLES[selected_style]}'!")
            logger.info(f"Изображение пользователя {user_id} успешно обработано в стиле '{selected_style}' и отправлено.")
        else:
            await message.reply_text("Произошла ошибка при обработке изображения.")
            logger.error(f"Функция apply_style вернула None для пользователя {user_id}, стиль '{selected_style}'.")
    elif not message.text:
        await message.reply_text("Я получил ваше сообщение, но пока могу обрабатывать только изображения после выбора стиля.")


# --- Настройка маршрута для вебхука ---
@app.route(f'/webhook/{TELEGRAM_TOKEN}', methods=['POST'])
async def telegram_webhook():
    """Получает обновления от Telegram и передает их в Application."""
    update_json = request.get_json()
    update = Update.de_json(update_json)
    await application.update_queue.put(update)
    return 'ok', 200

# --- Запуск веб-сервера Flask ---
if __name__ == '__main__':
    # Регистрируем обработчик сообщений и кнопок
    application.add_handler(MessageHandler(filters.TEXT | filters.PHOTO | filters.Document.IMAGE, handle_message))
    application.add_handler(CallbackQueryHandler(button))
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
