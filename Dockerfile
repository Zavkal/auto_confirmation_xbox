# Используем официальный Python образ как базовый
FROM python:3.13-slim

# Создаем и устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем system зависимости для Chrome/Chromium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    unzip \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libx11-6 \
    libxcomposite1 \
    libxcursor1 \
    libxdamage1 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    xdg-utils \
    fonts-liberation \
    chromium \
    && rm -rf /var/lib/apt/lists/*

COPY poetry.lock pyproject.toml ./
RUN pip install poetry
RUN poetry config virtualenvs.create false && poetry install --no-interaction --no-root

# Копируем ВСЕ файлы проекта (включая модули)
COPY . .

# Указываем команду для запуска вашего приложения
CMD ["python", "main.py"]