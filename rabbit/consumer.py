import logging
import time
import pika
from pika.exceptions import AMQPConnectionError, StreamLostError, ConnectionClosedByClient
from config import RABBITMQ_QUEUE_REQUEST, parameters
from rabbit.process_mq import process_message


logger = logging.getLogger(__name__)


def rabbitmq_consumer() -> None:
    """
    Основная функция consumer'а с автоматическим переподключением
    """
    retry_delay = 5  # секунд
    
    while True:
        try:
            _consume_messages()
        except (AMQPConnectionError, StreamLostError, ConnectionClosedByClient) as e:
            logger.error("Ошибка соединения с RabbitMQ: %s", e)
            logger.info("Попытка переподключения через %d секунд...", retry_delay)
            time.sleep(retry_delay)
        except KeyboardInterrupt:
            logger.info("Получен сигнал остановки. Завершение работы...")
            break
        except (OSError, IOError) as e:
            logger.error("Ошибка ввода-вывода: %s", e)
            logger.info("Попытка переподключения через %d секунд...", retry_delay)
            time.sleep(retry_delay)


def _consume_messages() -> None:
    """
    Функция для потребления сообщений с обработкой ошибок соединения
    """
    connection = None
    channel = None
    
    try:
        logger.info("Подключение к RabbitMQ...")
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()

        # Декларируем очередь (на случай, если она не создана)
        channel.queue_declare(queue=RABBITMQ_QUEUE_REQUEST, durable=True)
        logger.info("Подключение к очереди %s установлено", RABBITMQ_QUEUE_REQUEST)

        # Подписываемся на очередь
        channel.basic_consume(
            queue=RABBITMQ_QUEUE_REQUEST,
            on_message_callback=process_message,
            auto_ack=True
        )

        logger.info("Начинаем потребление сообщений...")
        channel.start_consuming()
        
    except (AMQPConnectionError, StreamLostError, ConnectionClosedByClient) as e:
        logger.error("Ошибка соединения во время потребления: %s", e)
        raise
    except (OSError, IOError) as e:
        logger.error("Ошибка ввода-вывода во время потребления: %s", e)
        raise
    finally:
        # Закрываем соединение при ошибке
        if channel and not channel.is_closed:
            try:
                channel.stop_consuming()
            except (OSError, IOError) as e:
                logger.warning("Ошибка при остановке потребления: %s", e)
        
        if connection and not connection.is_closed:
            try:
                connection.close()
            except (OSError, IOError) as e:
                logger.warning("Ошибка при закрытии соединения: %s", e)