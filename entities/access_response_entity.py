from dataclasses import dataclass
from enum import IntEnum, StrEnum


class AccessStatusError(IntEnum):
    SUCCESS = 0  # => Успешно
    CODE_ERROR = 1  # => Ошибка при вводе кода или пароля
    TWO_FA_ERROR = 2  # => Ошибка двухфакторной аутентификации
    PASSWORD_ERROR = 3  # => Ошибка пароля
    EMAIL_ERROR = 4  # => Ошибка почты
    CIRCULAR_WAIT_ERROR = 5  # => Ошибка циклического ожидания страницы
    STAY_LOG_IN_ERROR = 6  # => Ошибка остаться в системе
    AUTHENTICATOR_ERROR = 7  # => Ошибка аутентификатора
    UNKNOWN_ERROR = 8  # => Неизвестная ошибка
    SITE_ERROR = 9  # => Ошибка сайта
    CHECK_RECOVERY_MAIL_ERROR = 11  # => Ошибка проверки резервной почты
    FAQ_BUTTON_ERROR = 12  # => Ошибка кнопки 'Далее при подтвержедении условий'
    SECURITY_INFO_ACCURATE_ERROR = 13  # => Ошибка кнопки 'iLooksGood'


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


