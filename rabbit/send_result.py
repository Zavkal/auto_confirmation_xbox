import json
import logging

import pika

from config import parameters, RABBITMQ_QUEUE_RESPONSE

logger = logging.getLogger(__name__)

def send_result_message(result_data) -> None:
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Декларируем очередь для ответов
    channel.queue_declare(queue=RABBITMQ_QUEUE_RESPONSE, durable=True)

    channel.basic_publish(
        exchange='',
        routing_key=RABBITMQ_QUEUE_RESPONSE,
        body=json.dumps(result_data).encode('utf-8'),
        properties=pika.BasicProperties(
            delivery_mode=2  # делаем сообщение persistent
        )
    )

    logger.info(f"[>] Отправил результат: {result_data}")
    connection.close()