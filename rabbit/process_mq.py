import json

from adapters.base_adapter import SeleniumConfirmation


def process_message(ch, method, properties, body) -> None:
    data = json.loads(body.decode('utf-8'))
    adapter = SeleniumConfirmation()
    adapter.confirmation_code(data)