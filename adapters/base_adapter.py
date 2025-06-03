import copy
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
from seleniumbase.common.exceptions import TimeoutException

from rabbit.send_result import send_result_message

logger = logging.getLogger(__name__)


class SeleniumConfirmation:
    def __init__(self) -> None:
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

    def __del__(self) -> None:
        try:
            self.driver.quit()
            shutil.rmtree(self.user_data_dir, ignore_errors=True)
        except Exception as exc:
            logger.error(f"Ошибка при удалении временной папки: {exc}")

    def confirmation_code(self, data: dict[str, Any]) -> None:
        error_data = copy.deepcopy(data)
        code = data['code']
        email = data['login']
        password = data['password']
        data['success'] = 'False'
        data['error'] = 10
        send_result_message(data)
        logger.error(f"Отправил код 10. {data}")
        try:
            self.driver.get('https://login.live.com/oauth20_remoteconnect.srf')
            self.driver.find_element(By.ID, 'otc').send_keys(code)
            self.driver.find_element(By.ID, 'idSIButton9').click()
            time.sleep(10)
        except Exception as exc:
            logger.error(f"Ошибка при открытии страницы для входа в xbox {exc}")
            data['error'] = 9
            send_result_message(data)

        try:
            self.new_site(
                driver=self.driver,
                data=data,
                email=email,
                password=password,
                error_data=error_data,
            )
        except Exception as exc:
            logger.error(f"Ошибка при выполнении new_site: {exc}")
            # try:
            #     self.old_site(driver=self.driver,
            #                   data=data,
            #                   email=email,
            #                   password=password,
            #                   error_data=error_data)
            # except Exception as exc:
            #     logger.error(f"Ошибка при выполнении old_site: {exc}")
            #     error_data['error'] = 9
            #     error_data['success'] = 'False'
            # send_result_message(data)
            error_data['error'] = 9
            error_data['success'] = 'False'
            send_result_message(data)
        finally:
            self.driver.quit()

    @staticmethod
    def new_site(driver, data: dict[str, Any], email: str, password: str, error_data: dict[str, Any]) -> None:
        try:
            email_text = WebDriverWait(driver, 5).until(
                ec.presence_of_element_located((By.ID, 'usernameEntry'))
            )
            email_text.click()
            email_text.send_keys(email)

            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            ).click()
        except Exception as exc:
            logger.error(f"Ошибка при вводе email: {exc}")
            error_data['error'] = 1
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return
        try:
            driver.find_element(By.XPATH, "//*[contains(text(), \"Не удалось найти учетную запись Майкрософт\")]")
            error_data['error'] = 4
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")
            pass

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
            if password is None:
                raise Exception
            password_text = WebDriverWait(driver, 5).until(
                ec.presence_of_element_located((By.ID, 'passwordEntry')))
            password_text.click()
            password_text.send_keys(password)
            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            ).click()
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")
            driver.find_element(By.ID, "error")
            error_data['error'] = 3
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return

        try:
            logger.error("Ошибка пароля")
            driver.find_element(By.XPATH, "//*[contains(text(), \"Неправильный пароль для учетной записи Майкрософт.\")]")
            error_data['error'] = 3
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")

        try:
            logger.error("Ошибка: Введенный код истек")
            driver.find_element(By.XPATH, "//*[contains(text(), \"Получите новый код из устройства, на котором вы пытаетесь войти, и повторите попытку\")]")
            error_data['error'] = 1
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return
        except Exception as exc:
            logger.error(f"Ошибка при проверке наличия ошибки: {exc}")

        try:
            # => Кнопка остаться в системе
            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
            ).click()
            data['success'] = 'True'
            data['error'] = 0
            send_result_message(data)
            driver.quit()
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
            error_data['error'] = 2
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return

        try:
            # => Кнопка остаться в системе
            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
            ).click()
            data['success'] = 'True'
            data['error'] = 0
            send_result_message(data)
            driver.quit()
            return
        except Exception as e:
            logger.error(f"Ошибка при нажатии на кнопку 'secondaryButton': {e}")
            error_data['error'] = 2
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return

    @staticmethod
    def old_site(driver, data: dict[str, Any], email: str, password: str, error_data: dict[str, Any]) -> None:
        try:
            email_text = WebDriverWait(driver, 5).until(
                ec.presence_of_element_located((By.ID, 'i0116'))
            )
            email_text.click()
            email_text.send_keys(email)  # Кнопка ввода email
            driver.find_element(By.ID, 'idSIButton9').click()  # - Версия Димы
            try:
                # => Кнопка ввода пароля
                password_text = WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'i0118'))
                )
                password_text.click()
                password_text.send_keys(password)
                driver.find_element(By.ID, 'idSIButton9').click()  # - Версия Димы
            except Exception as exc:
                logger.error(f"Ошибка при вводе пароля: {exc}")
                data['success'] = 'False'
                data['error'] = 3
                send_result_message(data)
                driver.quit()
                return
            try:
                # => Кнопка остаться в системе
                WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located(
                        (By.ID, 'declineButton'))).click()
                data['success'] = 'True'
                data['error'] = 0
                send_result_message(data)
                driver.quit()
                return
            except TimeoutException:
                logger.error("TimeoutException: Кнопка 'declineButton' не найдена")
                pass

            try:
                while True:
                    # => После аутентификатора просит подтвердить.
                    # => Сделать проверку нахождения такой кнопки (Она может быть циклична)
                    WebDriverWait(driver, 5).until(
                        ec.presence_of_element_located(
                            (By.ID, 'iLooksGood')
                        )
                    ).click()
            except Exception as exc:
                logger.error(f"Ошибка при нажатии на кнопку 'iLooksGood': {exc}")

            try:
                # => Запрос аутентификатора после ввода пароля
                WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'inner')))
                error_data['error'] = 2
                error_data['success'] = 'False'
                send_result_message(error_data)
                driver.quit()
                return

            except Exception as exc:
                logger.error(f"Ошибка при ожидании элемента 'inner': {exc}")

            # => Кнопка "нет" при запросе остаться в системе
            WebDriverWait(driver, 5).until(
                ec.presence_of_element_located(
                    (By.ID, 'secondaryButton'))).click()
            data['success'] = 'True'
            data['error'] = 0
            send_result_message(data)
            driver.quit()
            return

        except Exception as exc:
            logger.error(f"Неизвестная ошибка: {exc}")
            error_data['error'] = 9
            error_data['success'] = 'False'
            send_result_message(data)
            driver.quit()
            return


if __name__ == '__main__':
    SeleniumConfirmation().confirmation_code(
        data={'code': 'UQWY7CU2', 'user_id': 1463186913, 'product_id': '281', 'order_id': 1414,
              'login': 'Dl2privat2@ya.ru', 'password': 'box22222', 'user_message_id': 29046,
              'product_title': 'Dying Light 2 - Ultimate', 'back_from': 'delivery', 'subs_period_id': None, 'error': 9,
              'success': 'False'})