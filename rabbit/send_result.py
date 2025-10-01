import json
import logging
import time
from dataclasses import asdict

import pika
from pika.exceptions import AMQPConnectionError, StreamLostError, ConnectionClosedByClient, ChannelClosedByBroker

from entities.access_response_entity import AccessResponseQueueEntity

logger = logging.getLogger(__name__)

class AccessResponsePublisher:
    def __init__(self, parameters: pika.ConnectionParameters, queue_name: str) -> None:
        self.parameters = parameters
        self.queue_name = queue_name
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self) -> None:
        """Устанавливает соединение с RabbitMQ"""
        try:
            self.connection = pika.BlockingConnection(self.parameters)
            self.channel = self.connection.channel()
            # Проверяем существующую очередь без изменения её параметров
            try:
                self.channel.queue_declare(queue=self.queue_name, passive=True)
            except ChannelClosedByBroker as e:
                if getattr(e, "reply_code", None) == 404:
                    # Очередь отсутствует - создадим без указания durable, чтобы не конфликтовать
                    if self.channel.is_closed:
                        self.channel = self.connection.channel()
                    self.channel.queue_declare(queue=self.queue_name)
                else:
                    raise
            logger.info("Соединение с очередью %s установлено", self.queue_name)
        except (AMQPConnectionError, StreamLostError, ConnectionClosedByClient, OSError, IOError) as e:
            logger.error("Ошибка подключения к RabbitMQ: %s", e)
            raise

    def _reconnect(self) -> None:
        """Переподключается к RabbitMQ"""
        logger.info("Попытка переподключения к RabbitMQ...")
        self._close_connection()
        time.sleep(2)  # Небольшая пауза перед переподключением
        self._connect()

    def _close_connection(self) -> None:
        """Безопасно закрывает соединение"""
        if self.channel and not self.channel.is_closed:
            try:
                self.channel.close()
            except (OSError, IOError) as e:
                logger.warning("Ошибка при закрытии канала: %s", e)
        
        if self.connection and not self.connection.is_closed:
            try:
                self.connection.close()
            except (OSError, IOError) as e:
                logger.warning("Ошибка при закрытии соединения: %s", e)

    def publish(self, *, entity: AccessResponseQueueEntity, max_retries: int = 3) -> None:
        """
        Публикует сообщение с автоматическим переподключением при ошибках
        """
        for attempt in range(max_retries):
            try:
                if not self.connection or self.connection.is_closed:
                    self._connect()
                
                body = json.dumps(asdict(entity)).encode("utf-8")
                self.channel.basic_publish(
                    exchange="",
                    routing_key=self.queue_name,
                    body=body,
                    properties=pika.BasicProperties(delivery_mode=2),  # Сохраняем сообщение на диск
                )
                logger.info("Отправлено сообщение в очередь -> %s: %s", self.queue_name, asdict(entity))
                return  # Успешная отправка
                
            except (AMQPConnectionError, StreamLostError, ConnectionClosedByClient) as e:
                logger.error("Ошибка соединения при отправке (попытка %d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    self._reconnect()
                else:
                    logger.error("Не удалось отправить сообщение после %d попыток", max_retries)
                    raise
            except (OSError, IOError) as e:
                logger.error("Ошибка ввода-вывода при отправке (попытка %d/%d): %s", attempt + 1, max_retries, e)
                if attempt < max_retries - 1:
                    self._reconnect()
                else:
                    raise

    def close_connection(self,) -> None:
        """Закрывает соединение"""
        self._close_connection()
