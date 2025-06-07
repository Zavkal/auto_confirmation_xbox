from dataclasses import dataclass


@dataclass
class AccessResponseQueueEntity:
    code: str
    user_id: int
    product_id: int
    order_id: int
    login: str
    password: str
    user_message_id: int
    product_title: str
    back_from: str
    subs_period_id: int | None = None
    success: str | None = None
    error: int | None = None