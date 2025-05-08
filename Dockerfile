# Используем официальный Python образ как базовый
FROM python:3.13-slim

# Устанавливаем Poetry
RUN pip install poetry

# Создаем и устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл pyproject.toml и poetry.lock
COPY pyproject.toml poetry.lock* /app/

# Устанавливаем зависимости с помощью Poetry
RUN poetry install --no-root --no-interaction

# Копируем остальные файлы (включая main.py)
COPY main.py .

# Указываем команду для запуска вашего приложения
CMD ["poetry", "run", "python", "main.py"]
