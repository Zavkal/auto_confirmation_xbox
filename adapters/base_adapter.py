import logging
import os
import shutil
import tempfile
import time
from typing import Any

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.chrome.options import Options as ChromeOptions

from entities.access_response_entity import AccessResponseQueueEntity, AccessStatusSolution, AccessStatusError
from rabbit.send_result import AccessResponsePublisher

logger = logging.getLogger(__name__)


class CustomExitException(BaseException):
    pass


class SeleniumConfirmation:
    def __init__(self, publisher: AccessResponsePublisher) -> None:
        self.options = ChromeOptions()
        self.options.add_argument('--incognito')
        self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument('--disable-gpu')
        self.user_data_dir = tempfile.mkdtemp()
        self.options.add_argument(f'--user-data-dir={self.user_data_dir}')
        self.driver = webdriver.Chrome(options=self.options)
        self.publisher = publisher
        self.entity = None


    def __del__(self) -> None:
        try:
            shutil.rmtree(self.user_data_dir, ignore_errors=True)
        except Exception as exc:
            logger.error(f"Ошибка при удалении временной папки: {exc}")



    def confirmation_code(self, data: dict[str, Any]) -> None:
        self.entity = AccessResponseQueueEntity(**data)
        self.entity.error = AccessStatusError.IN_PROGRESS
        self.entity.success = AccessStatusSolution.ERROR
        self.publisher.publish(entity=self.entity)
        try:
            self.driver.get('https://login.live.com/oauth20_remoteconnect.srf')
            self.new_site()

        except Exception as exc:
            logger.error(f"Ошибка при открытии страницы для входа в xbox {exc}")
            self.entity.error = AccessStatusError.SITE_ERROR
            self.publisher.publish(entity=self.entity)
            return

        except CustomExitException:
            pass

        finally:
            self.driver.quit()
            self.publisher.close_connection()


    def new_site(self) -> None:
        try:
            self.check_code()
            self.check_email()
            self.find_page()

        finally:
            self.publisher.publish(entity=self.entity)


    def check_code(self):
        try:
            WebDriverWait(self.driver, 5).until(
                ec.visibility_of_element_located((By.ID, 'otc'))
            )
            self.driver.find_element(By.ID, 'otc').send_keys(self.entity.code)
            self.driver.find_element(By.ID, 'idSIButton9').click()
        except Exception as exc:
            logging.error(f'Ошибка: Ошибка при вводе кода {exc}')
            self.entity.error = AccessStatusError.CODE_ERROR
            raise

        try:
            WebDriverWait(self.driver, 2).until(
                ec.visibility_of_element_located(
                    (By.XPATH,
                     "//*[contains(text(), \"Check the code and try again\")]")))
            logging.error(f'Ошибка: Код не верный')
            self.entity.error = AccessStatusError.CODE_ERROR
            raise CustomExitException
        except Exception as exc:
            logging.error(f'Ошибка: Ошибка при проверке ошибки {exc}')


    def check_email(self):
        try:
            email_text = WebDriverWait(self.driver, 5).until(
                ec.presence_of_element_located((By.ID, 'usernameEntry'))
            )
            email_text.click()
            email_text.send_keys(self.entity.login)

            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            ).click()
        except Exception as exc:
            logger.error(f"Ошибка при вводе email: {exc}")
            self.entity.error = AccessStatusError.EMAIL_ERROR
            raise

        try:
            WebDriverWait(self.driver, 2).until(
                ec.visibility_of_element_located((By.XPATH,
                                                  "//*[contains(text(), \"Try entering your details again, or create an account\")]")))
            self.entity.error = AccessStatusError.EMAIL_ERROR
            raise CustomExitException
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")


    def check_password(self):
        try:
            password_text = WebDriverWait(self.driver, 5).until(
                ec.presence_of_element_located((By.ID, 'passwordEntry')))
            password_text.click()
            password_text.send_keys(self.entity.password)
            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            ).click()
        except Exception as exc:
            logger.error(f"Ошибка при вводе пароля {exc}")
            self.entity.error = AccessStatusError.PASSWORD_ERROR
            raise

        try:
            self.driver.find_element(By.XPATH,
                                     "//*[contains(text(), \"password is incorrect\")]")
            self.entity.error = AccessStatusError.PASSWORD_ERROR
            logger.error("Ошибка пароля")
            raise CustomExitException
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")


    def check_other_login(self):
        try:
            WebDriverWait(self.driver, 3).until(
                ec.visibility_of_element_located((By.XPATH, "//*[text()='Other ways to sign in']"))
            ).click()
        except Exception as exc:
            logger.error(f"Ошибка при нажатии на кнопку 'Другие способы входа': {exc}")


    def check_use_password(self):
        try:
            WebDriverWait(self.driver, 3).until(
                ec.visibility_of_element_located((By.XPATH, "//*[text()='Use your password']"))
            ).click()
        except Exception as exc:
            logger.error(f"Ошибка при нажатии на кнопку 'Используйте свой пароль': {exc}")


    def check_code_expired(self):
        try:
            self.driver.find_element(By.XPATH,
                                     "//*[contains(text(), \"Get a new code from the device you're trying to sign in to and try again\")]")
            self.entity.error = AccessStatusError.CODE_ERROR
            logger.error("Ошибка: Введенный код истек")
            raise CustomExitException
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")


    def check_2fa(self):
        try:
            self.entity.error = AccessStatusError.AUTHENTICATOR_ERROR
            raise CustomExitException
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")


    def check_stay_log_in(self):
        try:
            # => Кнопка остаться в системе
            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
            ).click()
            time.sleep(5)
            self.entity.success = AccessStatusSolution.SUCCESS
            self.entity.error = AccessStatusError.SUCCESS
            raise CustomExitException
        except Exception as exc:
            logger.error(f"Ошибка при нажатии на кнопку 'secondaryButton': {exc}")
            self.entity.error = AccessStatusError.AUTHENTICATOR_ERROR
            raise


    def check_authenticator(self):
        try:
            # => Просит аутентификацию
            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable(
                    (By.ID, 'lightbox-cover'))).click()
        except Exception as e:
            logger.error(f"Ошибка при нажатии на элемент 'lightbox-cover': {e}")
            self.entity.error = AccessStatusError.AUTHENTICATOR_ERROR
            raise


    def check_recovery_mail(self):
        try:
            while True:
                # => После ввода пароля просит резерв почту
                WebDriverWait(self.driver, 5).until(
                    ec.element_to_be_clickable(
                        (By.ID, 'iShowSkip'))).click()
        except Exception as exc:
            logger.error(f"Ошибка при нажатии на кнопку 'iShowSkip': {exc}")


    def find_page(self):
        timeout = 10
        start_time = time.monotonic()

        while True:
            # Проверяем таймаут
            if time.monotonic() - start_time > timeout:
                logger.info("Таймер истёк. Прекращаем попытки.")
                self.entity.error = AccessStatusError.UNKNOWN_ERROR
                break

            try:
                self.driver.find_element(By.ID, 'passwordEntry')
                self.check_password()
                start_time = time.monotonic()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.XPATH, "//*[text()='Other ways to sign in']")
                self.check_other_login()
                start_time = time.monotonic()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.XPATH, "//*[text()='Use your password']")
                self.check_use_password()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.XPATH,
                                         "//*[contains(text(), \"Get a new code from the device you're trying to sign in to and try again\")]")
                self.check_code_expired()
                start_time = time.monotonic()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.XPATH,
                                         "//*[contains(text(), \"I have a code\")]")
                self.check_2fa()
                start_time = time.monotonic()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.XPATH,
                                         "//*[contains(text(), \"Don't recognize or have any of these\")]")
                self.check_2fa()
                start_time = time.monotonic()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.XPATH,
                                         "//*[contains(text(), \"approve request\")]")
                self.check_2fa()
                start_time = time.monotonic()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.ID, 'lightbox-cover')
                self.check_authenticator()
                start_time = time.monotonic()
            except Exception as exc:
                pass

            try:
                self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]')
                self.check_stay_log_in()
                start_time = time.monotonic()
            except Exception as exc:
                pass







if __name__ == '__main__':
    SeleniumConfirmation().confirmation_code(
        data={
    "code": "FGNR8UPN",
    "user_id": 1854450669,
    "product_id": "61",
    "order_id": 1581,
    "login": "Diablo2rent@outlook.com",
    "password": "rent2222",
    "user_message_id": 36112,
    "product_title": "Forza Horizon 3",
    "back_from": "delivery",
    "subs_period_id": 123,})


