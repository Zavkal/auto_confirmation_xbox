from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AccessStatusError(IntEnum):
    SUCCESS = 0  # => Успешно
    CODE_ERROR = 1  # => Ошибка при вводе кода или пароля
    AUTHENTICATOR_ERROR = 2  # => Ошибка аутентификатора
    PASSWORD_ERROR = 3  # => Ошибка пароля
    EMAIL_ERROR = 4  # => Ошибка почты
    UNKNOWN_ERROR = 8  # => Неизвестная ошибка
    SITE_ERROR = 9  # => Ошибка сайта
    IN_PROGRESS = 10  # => В работе


class AccessStatusSolution(StrEnum):
    SUCCESS = 'True'
    ERROR = 'False'


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
    success:  str | None = None
    error:  int | None = None


