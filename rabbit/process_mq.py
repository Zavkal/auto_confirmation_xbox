import json

from adapters.base_adapter import SeleniumConfirmation
from config import parameters, RABBITMQ_QUEUE_RESPONSE
from rabbit.send_result import AccessResponsePublisher


def process_message(ch, method, properties, body) -> None:
    response_rabbit = AccessResponsePublisher(parameters=parameters, queue_name=RABBITMQ_QUEUE_RESPONSE)
    data = json.loads(body.decode('utf-8'))
    adapter = SeleniumConfirmation(publisher=response_rabbit)
    adapter.confirmation_code(data)