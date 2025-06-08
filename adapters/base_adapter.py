import logging
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


class SeleniumConfirmation:
    def __init__(self, publisher: AccessResponsePublisher) -> None:
        self.options = ChromeOptions()
        self.options.add_argument('--incognito')
        # self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--lang=ru')
        self.user_data_dir = tempfile.mkdtemp()
        self.options.add_argument(f'--user-data-dir={self.user_data_dir}')
        self.driver = webdriver.Chrome(options=self.options)
        self.publisher = publisher


    def __del__(self) -> None:
        try:
            shutil.rmtree(self.user_data_dir, ignore_errors=True)
        except Exception as exc:
            logger.error(f"Ошибка при удалении временной папки: {exc}")


    def confirmation_code(self, data: dict[str, Any]) -> None:
        entity = AccessResponseQueueEntity(**data)
        entity.error = AccessStatusError.IN_PROGRESS.value
        entity.success = AccessStatusSolution.ERROR.value
        self.publisher.publish(entity=entity)
        logger.info(f"Отправил код 10 {data}")
        try:
            self.driver.get('https://login.live.com/oauth20_remoteconnect.srf')
            WebDriverWait(self.driver, 5).until(
                ec.visibility_of_element_located((By.ID, 'otc'))
            )
            self.driver.find_element(By.ID, 'otc').send_keys(entity.code)
            self.driver.find_element(By.ID, 'idSIButton9').click()
            time.sleep(10)
            self.new_site(
                driver=self.driver,
                entity=entity,
                publisher=self.publisher
            )
        except Exception as exc:
            logger.error(f"Ошибка при открытии страницы для входа в xbox {exc}")
            entity.error = AccessStatusError.SITE_ERROR.value
            self.publisher.publish(entity=entity)
            return

        finally:
            self.driver.quit()
            self.publisher.close_connection()


    @staticmethod
    def new_site(driver, entity: AccessResponseQueueEntity, publisher: AccessResponsePublisher) -> None:
        try:
            try:
                WebDriverWait(driver, 2).until(
                    ec.visibility_of_element_located((By.XPATH, "//*[contains(text(), \"Этот код не подошел. Проверьте код и повторите попытку.\")]")))
                logging.error(f'Ошибка: Код не верный')
                entity.error = AccessStatusError.CODE_ERROR.value
                return
            except Exception as exc:
                logging.error(f'Ошибка: Ошибка при проверке ошибки {exc}')

            try:
                email_text = WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'usernameEntry'))
                )
                email_text.click()
                email_text.send_keys(entity.login)

                WebDriverWait(driver, 5).until(
                    ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
                ).click()
            except Exception as exc:
                logger.error(f"Ошибка при вводе email: {exc}")
                entity.error = AccessStatusError.EMAIL_ERROR.value
                return
            try:
                WebDriverWait(driver, 2).until(
                    ec.visibility_of_element_located((By.XPATH, "//*[contains(text(), \"Попробуйте ввести свои данные еще раз или создайте учетную запись.\")]")))
                entity.error = AccessStatusError.EMAIL_ERROR.value
                return
            except Exception as exc:
                logger.error(f"Ошибка при проверке наличия ошибки: {exc}")

            try:
                WebDriverWait(driver, 3).until(
                    ec.presence_of_element_located((By.XPATH, "//*[text()='Другие способы входа']"))
                ).click()
            except Exception as exc:
                logger.error(f"Ошибка при повторном нажатии на кнопку 'Другие способы входа': {exc}")

            try:
                WebDriverWait(driver, 3).until(
                    ec.presence_of_element_located((By.XPATH, "//*[text()='Используйте свой пароль']"))
                ).click()
            except Exception as exc:
                logger.error(f"Ошибка при повторном нажатии на кнопку 'Используйте свой пароль': {exc}")

            try:
                WebDriverWait(driver, 3).until(
                    ec.presence_of_element_located((By.ID, 'fui-CardHeader__header30'))
                ).click()
            except Exception as exc:
                logger.error(f"Ошибка при нажатии на элемент 'fui-CardHeader__header30': {exc}")

            try:
                WebDriverWait(driver, 3).until(
                    ec.presence_of_element_located((By.ID, 'idA_PWD_SwitchToPassword'))
                ).click()
            except Exception as exc:
                logger.error(f"Ошибка при нажатии на элемент 'idA_PWD_SwitchToPassword': {exc}")

            try:
                if entity.password is None:
                    raise Exception
                password_text = WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'passwordEntry')))
                password_text.click()
                password_text.send_keys(entity.password)
                WebDriverWait(driver, 5).until(
                    ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
                ).click()
            except Exception as exc:
                logger.error(f"Ошибка при проверке наличия ошибки: {exc}")
                driver.find_element(By.ID, "error")
                entity.error = AccessStatusError.PASSWORD_ERROR.value
                return

            try:
                logger.error("Ошибка пароля")
                driver.find_element(By.XPATH, "//*[contains(text(), \"Неправильный пароль для учетной записи Майкрософт.\")]")
                entity.error = AccessStatusError.PASSWORD_ERROR.value
                return
            except Exception as exc:
                logger.error(f"Ошибка при проверке наличия ошибки: {exc}")

            try:
                logger.error("Ошибка: Введенный код истек")
                driver.find_element(By.XPATH, "//*[contains(text(), \"Получите новый код из устройства, на котором вы пытаетесь войти, и повторите попытку\")]")
                entity.error = AccessStatusError.CODE_ERROR.value
                return
            except Exception as exc:
                logger.error(f"Ошибка при проверке наличия ошибки: {exc}")

            try:
                # => Кнопка остаться в системе
                WebDriverWait(driver, 5).until(
                    ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
                ).click()
                entity.success = AccessStatusSolution.SUCCESS.value
                entity.error = AccessStatusError.SUCCESS.value
                return
            except Exception as exc:
                logger.error(f"Ошибка при нажатии на кнопку 'secondaryButton': {exc}")
            try:
                while True:
                    # => После ввода пароля просит резерв почту
                    WebDriverWait(driver, 5).until(
                        ec.element_to_be_clickable(
                            (By.ID, 'iShowSkip'))).click()
            except Exception as exc:
                logger.error(f"Ошибка при нажатии на кнопку 'iShowSkip': {exc}")
            try:
                # => Просит аутентификацию
                WebDriverWait(driver, 5).until(
                    ec.element_to_be_clickable(
                        (By.ID, 'lightbox-cover'))).click()
            except Exception as e:
                logger.error(f"Ошибка при нажатии на элемент 'lightbox-cover': {e}")
                entity.error = AccessStatusError.AUTHENTICATOR_ERROR.value
                return

            try:
                # => Кнопка остаться в системе
                WebDriverWait(driver, 5).until(
                    ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
                ).click()
                entity.success = AccessStatusSolution.SUCCESS.value
                entity.error = AccessStatusError.SUCCESS.value
                return
            except Exception as e:
                logger.error(f"Ошибка при нажатии на кнопку 'secondaryButton': {e}")
                entity.error = AccessStatusError.AUTHENTICATOR_ERROR.value
                return
        finally:
            publisher.publish(entity=entity)


if __name__ == '__main__':
    SeleniumConfirmation().confirmation_code(
        data={'code': 'UQWY7CU2', 'user_id': 1463186913, 'product_id': '281', 'order_id': 1414,
              'login': 'Dl2privat2@ya.ru', 'password': 'box22222', 'user_message_id': 29046,
              'product_title': 'Dying Light 2 - Ultimate', 'back_from': 'delivery', 'subs_period_id': None, 'error': 9,
              'success': 'False'})

