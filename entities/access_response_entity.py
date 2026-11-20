from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AccessStatusError(IntEnum):
    SUCCESS = 0  # => Успешно
    CODE_ERROR = 1  # => Ошибка при вводе кода
    PASSWORD_ERROR = 2  # => Ошибка пароля
    EMAIL_ERROR = 3  # => Ошибка почты
    STAY_LOG_IN_ERROR = 4  # => Ошибка остаться в системе
    AUTHENTICATOR_ERROR = 5  # => Ошибка аутентификатора
    SECURITY_INFO_ACCURATE_ERROR = 6  # => Ошибка кнопки 'iLooksGood'
    OLD_LOGIN_METHOD_ERROR = 7  # => Старый метод входа
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
    auth_base_code: str | None = None
    success:  str | None = None
    error:  int | None = None


