# from adapters.base_adapter import SeleniumConfirmation, Ass
from rabbit.consumer import rabbitmq_consumer

if __name__ == '__main__':
    rabbitmq_consumer()

    # SeleniumConfirmation(publisher=Ass()).confirmation_code( # debug mode
    # data={
    #     "code": "dryvcae3",
    #     "user_id": 1,
    #     "product_id": "61",
    #     "order_id": 1581,
    #     "login": "MouseRent@outlook.com",
    #     "password": "123",
    #     "user_message_id": 36112,
    #     "product_title": "Forza Horizon 3",
    #     "auth_base_code": "123",
    #     "back_from": "delivery",
    #     "subs_period_id": 123,
    #     }
    # )