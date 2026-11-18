import logging
import os
import pika
from dotenv import load_dotenv

load_dotenv()

RABBITMQ_USER = str(os.getenv("RABBITMQ_USER"))
RABBITMQ_PASS = str(os.getenv("RABBITMQ_PASS"))
RABBITMQ_HOST = str(os.getenv("RABBITMQ_HOST"))
RABBITMQ_QUEUE_REQUEST = str(os.getenv("RABBITMQ_QUEUE_REQUEST"))
RABBITMQ_QUEUE_RESPONSE = str(os.getenv("RABBITMQ_QUEUE_RESPONSE"))

credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASS)
parameters = pika.ConnectionParameters(
    host=RABBITMQ_HOST,
    port=5672,
    credentials=credentials,
    heartbeat=600,  # Heartbeat каждые 10 минут
    blocked_connection_timeout=300,  # Таймаут блокировки соединения 5 минут
    connection_attempts=3,  # Количество попыток подключения
    retry_delay=2,  # Задержка между попытками подключения
    socket_timeout=10,  # Таймаут сокета
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
