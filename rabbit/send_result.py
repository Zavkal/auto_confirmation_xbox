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

class AccessRequestPublisher:
    def __init__(self, host: str, user: str, password: str, queue_name: str) -> None:
        self.rabbitmq_host = host
        self.rabbitmq_user = user
        self.rabbitmq_pass = password
        self.queue_name = queue_name

    def _connect(self):
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=self.rabbitmq_host,
                credentials=pika.PlainCredentials(self.rabbitmq_user, self.rabbitmq_pass),
            )
        )
        channel = connection.channel()
        channel.queue_declare(queue=self.queue_name)
        return connection, channel

    def publish(self, *, entity: AccessRequestQueueEntity) -> None:
        body = json.dumps(asdict(entity)).encode("utf-8")

        connection, channel = self._connect()
        try:
            channel.basic_publish(
                exchange="",
                routing_key=self.queue_name,
                body=body,
                properties=pika.BasicProperties(delivery_mode=1),
            )
            logger.info(f"Отправлено сообщение в очередь -> {self.queue_name}: {asdict(entity)}")
        finally:
            channel.close()
            connection.close()