import json
import logging
from dataclasses import asdict

import pika

from entities.access_response_entity import AccessResponseQueueEntity

logger = logging.getLogger(__name__)

class AccessResponsePublisher:
    def __init__(self, parameters: pika.ConnectionParameters, queue_name: str) -> None:
        self.parameters = parameters
        self.queue_name = queue_name
        self.connection = pika.BlockingConnection(
            self.parameters
        )
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue_name, durable=True)


    def publish(self, *, entity: AccessResponseQueueEntity, ) -> None:
        body = json.dumps(asdict(entity)).encode("utf-8")
        self.channel.basic_publish(
            exchange="",
            routing_key=self.queue_name,
            body=body,
            properties=pika.BasicProperties(delivery_mode=1),
        )
        logger.info(f"Отправлено сообщение в очередь -> {self.queue_name}: {asdict(entity)}")


    def close_connection(self,) -> None:
        self.channel.close()
        self.connection.close()
