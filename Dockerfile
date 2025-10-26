FROM python:3.13-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libc6 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf-2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Установка Google Chrome (современный способ без apt-key)
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /usr/share/keyrings/google-linux-signing-keyring.gpg && \
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-linux-signing-keyring.gpg] https://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Установка uv
RUN pip install uv

# Создание рабочей директории
WORKDIR /app

# Создание директорий для логов и скриншотов
RUN mkdir -p /app/logs /app/screenshots

# Копирование только файлов зависимостей для кэширования слоёв
COPY pyproject.toml uv.lock* ./

# Установка зависимостей (используем lock-файл, если он присутствует)
RUN if [ -f uv.lock ]; then uv sync --frozen; else uv sync; fi

# Точка входа будет использовать код из volume mount
CMD ["uv", "run", "python", "main.py"]