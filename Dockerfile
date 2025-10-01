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
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Установка Google Chrome
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" \
    > /etc/apt/sources.list.d/google-chrome.list && \
    apt-get update && apt-get install -y google-chrome-stable && \
    rm -rf /var/lib/apt/lists/*

# Установка uv
RUN pip install uv

# Создание рабочей директории
WORKDIR /app

# Создание директории для логов
RUN mkdir -p /app/logs

# Копирование исходного кода (включая pyproject.toml и, при наличии, uv.lock)
COPY . .

# Установка зависимостей (используем lock-файл, если он присутствует)
RUN if [ -f uv.lock ]; then uv sync --frozen; else uv sync; fi

CMD ["uv", "run", "python", "main.py"]