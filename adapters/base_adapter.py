from datetime import datetime
import logging
import os
import shutil
import tempfile
import time
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.chrome.options import Options as ChromeOptions

from entities.access_response_entity import AccessResponseQueueEntity, AccessStatusSolution, AccessStatusError
from rabbit.send_result import AccessResponsePublisher
from src.totp_service import generate_totp

logger = logging.getLogger(__name__)


def _short_exception(exc: Exception) -> str:
    text = str(exc)
    return text.split("Stacktrace:")[0].strip()


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
        self._password_submitted = False
        self._use_password_clicked = False
        self._other_login_clicked = False
        self._totp_submitted = False


    def __del__(self) -> None:
        try:
            shutil.rmtree(self.user_data_dir, ignore_errors=True)
        except Exception as exc:
            logger.error("Ошибка при удалении временной папки: %s", _short_exception(exc))


    def create_screenshot(self):
        """Сохраняет скриншот в папку screenshots/ (создаёт её если нет)."""
        debug = False
        if debug:
            os.makedirs('screenshots', exist_ok=True)
            filename = os.path.join('screenshots', datetime.now().strftime('%Y-%m-%d_%H-%M-%S') + '_debug_screenshot.png')
            try:
                self.driver.save_screenshot(filename)
                logger.info(f"Скриншот сохранён: {filename}")
            except Exception as exc:
                logger.error("Ошибка при создании скриншота: %s", _short_exception(exc))


    def confirmation_code(self, data: dict[str, Any]) -> None:
        self.entity = AccessResponseQueueEntity(**data)
        self.entity.error = AccessStatusError.IN_PROGRESS
        self.entity.success = AccessStatusSolution.ERROR
        self.publisher.publish(entity=self.entity)
        try:
            if not (self.entity.auth_base_code or "").strip():
                logger.error("auth_base_code пустой — завершаем вход")
                time.sleep(3)
                self.entity.error = AccessStatusError.OLD_LOGIN_METHOD_ERROR
                self.publisher.publish(entity=self.entity)
                return
            self.driver.get('https://login.live.com/oauth20_remoteconnect.srf')
            self.new_site()

        except Exception as exc:
            logger.error("Ошибка при открытии страницы для входа в xbox %s", _short_exception(exc))
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
            self.find_page()

        finally:
            self.create_screenshot()
            self.publisher.publish(entity=self.entity)


    def check_code(self):
        try:
            WebDriverWait(self.driver, 5).until(
                ec.visibility_of_element_located((By.ID, 'otc'))
            )
            self.driver.find_element(By.ID, 'otc').send_keys(self.entity.code)
            self.driver.find_element(By.ID, 'idSIButton9').click()
        except Exception as exc:
            logging.error('Ошибка: Ошибка при вводе кода %s', _short_exception(exc))
            self.entity.error = AccessStatusError.CODE_ERROR
            raise

        try:
            WebDriverWait(self.driver, 2).until(
                ec.visibility_of_element_located(
                    (By.XPATH,
                     "//*[contains(text(), \"Check the code and try again\")]")))
            logging.error('Ошибка: Код не верный')
            self.entity.error = AccessStatusError.CODE_ERROR
            self.create_screenshot()
            raise CustomExitException
        except Exception as exc:
            logging.error('Ошибка: Ошибка при проверке ошибки %s', _short_exception(exc))
            self.create_screenshot()


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
            logger.error("Ошибка при вводе email: %s", _short_exception(exc))
            self.entity.error = AccessStatusError.EMAIL_ERROR
            self.create_screenshot()
            raise

        try:
            WebDriverWait(self.driver, 2).until(
                ec.visibility_of_element_located((By.XPATH,
                                                  "//*[contains(text(), \"Try entering your details again, or create an account\")]")))
            self.entity.error = AccessStatusError.EMAIL_ERROR
            self.create_screenshot()
            raise CustomExitException
        except Exception as exc:
            logger.error("Ошибка при проверке наличия ошибки: %s", _short_exception(exc))
            self.create_screenshot()


    def check_password(self) -> bool:
        if self._password_submitted:
            return True
        try:
            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable((By.ID, 'passwordEntry')))
            field = self.driver.find_element(By.ID, 'passwordEntry')
            field.click()
            field = self.driver.find_element(By.ID, 'passwordEntry')
            field.clear()
            field = self.driver.find_element(By.ID, 'passwordEntry')
            field.send_keys(self.entity.password)
            submit = WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            )
            self._native_click(submit)
            WebDriverWait(self.driver, 10).until(
                lambda d: not self._first_visible(By.ID, 'passwordEntry')
                or self._first_visible(By.XPATH, "//*[contains(text(), 'password is incorrect')]")
            )
            self._password_submitted = True
        except Exception as extra:
            logger.error("Ошибка при вводе пароля %s", _short_exception(extra))
            self.entity.error = AccessStatusError.PASSWORD_ERROR
            self.create_screenshot()
            return False

        try:
            WebDriverWait(self.driver, 2).until(
                ec.visibility_of_element_located((By.XPATH,
                    "//*[contains(text(), 'password is incorrect')]"))
            )
            self.entity.error = AccessStatusError.PASSWORD_ERROR
            logger.error("Ошибка пароля")
            self.create_screenshot()
            raise CustomExitException
        except CustomExitException:
            raise
        except Exception:
            return True

    def check_other_login(self):
        try:
            btn = WebDriverWait(self.driver, 3).until(
                ec.element_to_be_clickable(self._other_ways_locator())
            )
            self._native_click(btn)
        except Exception as exc:
            logger.error("Ошибка при нажатии на кнопку 'Другие способы входа': %s", _short_exception(exc))
            self.create_screenshot()

    def check_use_password(self) -> bool:
        if self._use_password_clicked:
            return True
        try:
            btn = WebDriverWait(self.driver, 3).until(
                ec.element_to_be_clickable(self._use_password_locator())
            )
            self._native_click(btn)
            self._use_password_clicked = True
            return True
        except Exception as exc:
            logger.error("Ошибка при нажатии на кнопку 'Используйте свой пароль': %s", _short_exception(exc))
            self.create_screenshot()
            return False

    def check_code_expired(self):
        try:
            self.driver.find_element(By.XPATH,
                                     "//*[contains(text(), \"Get a new code from the device you're trying to sign in to and try again\")]")
            self.entity.error = AccessStatusError.CODE_ERROR
            self.create_screenshot()
            logger.error("Ошибка: Введенный код истек")
            raise CustomExitException
        except Exception as exc:
            logger.error("Ошибка при проверке наличия ошибки: %s", _short_exception(exc))
            self.create_screenshot()

    def _totp_title_locator(self) -> tuple[str, str]:
        return (
            By.XPATH,
            "//h1[@data-testid='title']"
            "[contains(., 'Enter the code generated by your authenticator app')]",
        )

    def _is_totp_window(self) -> bool:
        return bool(self._first_visible(*self._totp_title_locator()))

    def _totp_input_locator(self) -> tuple[str, str]:
        return (
            By.XPATH,
            "//label[normalize-space()='Code']"
            "/ancestor::span[contains(@class,'fui-Input')]"
            "//input[contains(@class,'fui-Input__input')]",
        )

    def enter_authenticator_code(self) -> bool:
        if self._totp_submitted:
            return True
        secret = (self.entity.auth_base_code or "").strip() if self.entity else ""
        if not secret:
            logger.error("auth_base_code пустой — завершаем вход")
            self.entity.error = AccessStatusError.AUTHENTICATOR_ERROR
            self.create_screenshot()
            raise CustomExitException
        try:
            otp = generate_totp(secret)
            field = WebDriverWait(self.driver, 10).until(
                ec.element_to_be_clickable(self._totp_input_locator())
            )
            field.click()
            field = self.driver.find_element(*self._totp_input_locator())
            field.clear()
            field = self.driver.find_element(*self._totp_input_locator())
            field.send_keys(otp)
            submit = WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable(
                    (By.CSS_SELECTOR, 'button[data-testid="primaryButton"]')
                )
            )
            self._native_click(submit)
            WebDriverWait(self.driver, 10).until(
                lambda d: not self._first_visible(*self._totp_title_locator())
            )
            self._totp_submitted = True
            return True
        except CustomExitException:
            raise
        except Exception as exc:
            logger.error("Ошибка при вводе кода аутентификатора: %s", _short_exception(exc))
            self.entity.error = AccessStatusError.AUTHENTICATOR_ERROR
            self.create_screenshot()
            raise CustomExitException

    def check_stay_log_in(self):
        try:
            WebDriverWait(self.driver, 5).until(
                ec.visibility_of_element_located(
                    (By.XPATH, "//h1[contains(., 'Stay signed in')]")
                )
            )
            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
            ).click()
            time.sleep(5)
            self.entity.success = AccessStatusSolution.SUCCESS
            self.entity.error = AccessStatusError.SUCCESS
            raise CustomExitException
        except Exception as exc:
            logger.error("Ошибка при нажатии на кнопку 'secondaryButton': %s", _short_exception(exc))
            self.entity.error = AccessStatusError.STAY_LOG_IN_ERROR
            self.create_screenshot()
            raise


    def security_info_accurate(self):
        try:
            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable(
                    (By.ID, 'iLooksGood'))).click()
        except Exception as exc:
            logger.error("Ошибка при нажатии на кнопку 'iLooksGood': %s", _short_exception(exc))
            self.entity.error = AccessStatusError.SECURITY_INFO_ACCURATE_ERROR
            self.create_screenshot()

    def _use_password_locator(self) -> tuple[str, str]:
        return (
            By.XPATH,
            "//*[self::a or self::button or @role='button']"
            "[contains(normalize-space(.), 'Use your password')]"
            "[not(.//*[self::a or self::button or @role='button'])]",
        )

    def _other_ways_locator(self) -> tuple[str, str]:
        return (
            By.XPATH,
            "//*[self::a or self::button or @role='button']"
            "[contains(normalize-space(.), 'Other ways to sign in')]"
            "[not(.//*[self::a or self::button or @role='button'])]",
        )

    def _first_visible(self, by, value):
        for el in self.driver.find_elements(by, value):
            try:
                if el.is_displayed():
                    return el
            except Exception:
                continue
        return None

    def _native_click(self, element) -> None:
        self.driver.execute_script(
            "arguments[0].scrollIntoView({block:'center', inline:'nearest'});",
            element,
        )
        time.sleep(0.25)
        try:
            ActionChains(self.driver).move_to_element(element).pause(0.15).click().perform()
        except Exception:
            try:
                element.click()
            except ElementClickInterceptedException:
                self.driver.execute_script("arguments[0].click();", element)

    def find_page(self):
        timeout = 15
        max_total_time = 60
        start_time = time.monotonic()
        overall_start_time = start_time

        while True:
            now = time.monotonic()
            if now - overall_start_time > max_total_time:
                logger.info("Общий таймер входа истёк. Прекращаем попытки.")
                self.entity.error = AccessStatusError.UNKNOWN_ERROR
                self.create_screenshot()
                break
            if now - start_time > timeout:
                logger.info("Таймер истёк. Прекращаем попытки.")
                self.entity.error = AccessStatusError.UNKNOWN_ERROR
                self.create_screenshot()
                break

            if self._first_visible(By.ID, 'usernameEntry'):
                try:
                    self.check_email()
                    start_time = time.monotonic()
                except Exception:
                    pass

            if self._first_visible(By.ID, 'passwordEntry'):
                if self.check_password():
                    start_time = time.monotonic()
                continue

            if self._first_visible(*self._use_password_locator()):
                if self.check_use_password():
                    start_time = time.monotonic()
                continue

            if (
                not self._password_submitted
                and not self._first_visible(By.ID, 'passwordEntry')
                and self._first_visible(*self._other_ways_locator())
                and not self._other_login_clicked
            ):
                self.check_other_login()
                self._other_login_clicked = True
                start_time = time.monotonic()
                continue

            if self._is_totp_window():
                self.enter_authenticator_code()
                start_time = time.monotonic()
                continue

            if not self._totp_submitted:
                time.sleep(0.5)
                continue

            try:
                self.driver.find_element(By.XPATH,
                                         "//*[contains(text(), \"Get a new code from the device you're trying to sign in to and try again\")]")
                self.check_code_expired()
                start_time = time.monotonic()
            except Exception:
                pass

            try:
                self.driver.find_element(By.XPATH, "//h1[contains(., 'Stay signed in')]")
                self.check_stay_log_in()
                start_time = time.monotonic()
            except Exception:
                pass

            try:
                self.driver.find_element(By.ID, 'iLooksGood')
                self.security_info_accurate()
                start_time = time.monotonic()
            except Exception:
                pass

            try:
                self.driver.find_element(By.ID, 'idDiv_Finish_Title')
                self.entity.success = AccessStatusSolution.SUCCESS
                self.entity.error = AccessStatusError.SUCCESS
                raise CustomExitException
            except Exception:
                pass

            time.sleep(0.5)


class Ass:

    def publish(self, *args, **kwargs):
        pass
    
    def close_connection(self, *args, **kwargs):
        pass