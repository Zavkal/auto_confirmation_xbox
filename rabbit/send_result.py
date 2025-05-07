import json

import pika

from config import parameters, RABBITMQ_QUEUE_RESPONSE


def send_result_message(result_data):
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

    print(f"[>] Отправил результат: {result_data}")
    connection.close()