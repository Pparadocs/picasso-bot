# Используем официальный Python-образ
FROM python:3.13-slim

# Устанавливаем системные зависимости для Pillow
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg-dev \
    zlib1g-dev \
    libtiff-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    libopenjp2-7-dev \
    libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем Python-зависимости
COPY requirements2.txt .
RUN pip install --no-cache-dir -r requirements2.txt

# Копируем код
COPY main2.py .

# Указываем команду запуска
CMD ["python", "main2.py"]
