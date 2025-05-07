import pika

from config import RABBITMQ_QUEUE_REQUEST, parameters
from rabbit.process_mq import process_message


def rabbitmq_consumer():
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()

    # Декларируем очередь (на случай, если она не создана)
    channel.queue_declare(queue=RABBITMQ_QUEUE_REQUEST)

    # Подписываемся на очередь
    channel.basic_consume(
        queue=RABBITMQ_QUEUE_REQUEST,
        on_message_callback=process_message,
        auto_ack=True
    )

    channel.start_consuming()
