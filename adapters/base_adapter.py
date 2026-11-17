from datetime import datetime
import logging
import os
import shutil
import tempfile
import time
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import ElementClickInterceptedException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.chrome.options import Options as ChromeOptions

from config import IMAP_EMAIL, IMAP_PASS, RECOVERY_EMAIL
from entities.access_response_entity import AccessResponseQueueEntity, AccessStatusSolution, AccessStatusError
from rabbit.send_result import AccessResponsePublisher
from src.get_last_mail_service import GetLastMailService
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
        self.mail_service = GetLastMailService()
        self.mail_service.prime({"email": IMAP_EMAIL, "password": IMAP_PASS})
        self._sent_recovery_option = False
        self._submitted_recovery_email = False
        self._skip_recovery = False
        self._reported_missing_recovery = False
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

    def check_2fa(self):
        try:
            self.entity.error = AccessStatusError.TWO_FA_ERROR
            self.create_screenshot()
            raise CustomExitException
        except Exception as exc:
            logger.error("Ошибка при проверке наличия ошибки: %s", _short_exception(exc))
            self.create_screenshot()

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


    # def check_authenticator(self):
    #     try:
    #         # => Просит аутентификацию
    #         WebDriverWait(self.driver, 5).until(
    #             ec.element_to_be_clickable(
    #                 (By.ID, 'lightbox-cover'))).click()
    #     except Exception as e:
    #         logger.error("Ошибка при нажатии на элемент 'lightbox-cover': %s", _short_exception(e))
    #         self.entity.error = AccessStatusError.AUTHENTICATOR_ERROR
    #         self.create_screenshot()
    #         raise


    # def check_recovery_mail(self):
    #     try:
    #         # => После ввода пароля просит резерв почту
    #         WebDriverWait(self.driver, 5).until(
    #             ec.element_to_be_clickable(
    #                 (By.ID, 'iShowSkip'))).click()
    #     except Exception as exc:
    #         logger.error("Ошибка при нажатии на кнопку 'iShowSkip': %s", _short_exception(exc))
    #         self.entity.error = AccessStatusError.CHECK_RECOVERY_MAIL_ERROR
    #         self.create_screenshot()


    # def check_faq_button(self):
    #     try:
    #         WebDriverWait(self.driver, 5).until(
    #             ec.element_to_be_clickable(
    #                 (By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))).click()
    #     except Exception as exc:
    #         logger.error("Ошибка при нажатии на кнопку 'Далее при подтвержеднии условий': %s", _short_exception(exc))
    #         self.entity.error = AccessStatusError.FAQ_BUTTON_ERROR
    #         self.create_screenshot()


    def security_info_accurate(self):
        try:
            WebDriverWait(self.driver, 5).until(
                ec.element_to_be_clickable(
                    (By.ID, 'iLooksGood'))).click()
        except Exception as exc:
            logger.error("Ошибка при нажатии на кнопку 'iLooksGood': %s", _short_exception(exc))
            self.entity.error = AccessStatusError.SECURITY_INFO_ACCURATE_ERROR
            self.create_screenshot()

    def _masked_recovery_email(self) -> str:
        local, domain = RECOVERY_EMAIL.split("@", 1)
        return local[:2] + ("*" * 5) + "@" + domain

    def _send_code_to_locator(self) -> tuple[str, str]:
        local, domain = RECOVERY_EMAIL.split("@", 1)
        prefix = local[:2]
        return (
            By.XPATH,
            "//*[(self::button or @role='button')]"
            f"[contains(normalize-space(.), 'Send a code to {prefix}')]"
            f"[contains(normalize-space(.), '@{domain}')]"
            "[not(.//*[@role='button' or self::button])]",
        )

    def _has(self, by, value) -> bool:
        return bool(self.driver.find_elements(by, value))

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

    def _could_not_send_code(self) -> bool:
        return bool(self._first_visible(
            By.XPATH,
            "//*[contains(., \"We couldn't send the code\") or "
            "contains(., 'could not send the code')]",
        ))

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

    def _mark_missing_recovery_mail(self) -> None:
        if self._reported_missing_recovery:
            return
        self._reported_missing_recovery = True
        login = self.entity.login if self.entity else "?"
        logger.warning("Нету почты в аккаунте: %s", login)
        self.entity.error = AccessStatusError.NO_RECOVERY_MAIL
        self.publisher.publish(entity=self.entity)

    def _recovery_options_without_our_mail(self) -> bool:
        if self._has(*self._send_code_to_locator()):
            return False
        return bool(
            self._first_visible(By.XPATH, "//h1[contains(., 'Sign in another way')]")
            or self._first_visible(By.XPATH, "//h1[contains(., 'Verify your identity')]")
            or self._first_visible(By.XPATH, "//h1[contains(., 'Help us protect')]")
        )

    def _is_approve_sign_in_page(self) -> bool:
        if self._first_visible(*self._send_code_to_locator()):
            return False
        if self._first_visible(
            By.XPATH,
            "//*[(self::button or @role='button')]"
            "[contains(normalize-space(.), 'Approve sign-in with a mobile app')]",
        ):
            return False
        return bool(
            self._first_visible(
                By.XPATH,
                "//*[contains(translate(., 'APPROVE', 'approve'), 'approve') and "
                "contains(translate(., 'REQUEST', 'request'), 'request')]",
            )
            or self._first_visible(By.XPATH, "//*[contains(., 'Are you trying to sign in')]")
        )

    def _recovery_next_screen_opened(self, driver) -> bool:
        return bool(
            self._first_visible(By.ID, "proof-confirmation-email-input")
            or self._first_visible(By.CSS_SELECTOR, "input[autocomplete='one-time-code']")
            or self._first_visible(By.XPATH, "//*[contains(., 'Enter your code')]")
            or self._first_visible(By.XPATH, "//h1[contains(., 'Verify your email')]")
        )

    def check_recovery_mail(self) -> bool:
        if self._sent_recovery_option:
            return True
        try:
            locator = self._send_code_to_locator()
            btn = WebDriverWait(self.driver, 15).until(
                ec.visibility_of_element_located(locator)
            )
            if "Send a code to" not in (btn.text or ""):
                raise AssertionError(f"нашли не ту кнопку: {btn.text!r}")
            self._native_click(btn)
            try:
                WebDriverWait(self.driver, 4).until(self._recovery_next_screen_opened)
            except TimeoutException:
                if self._first_visible(*locator):
                    primary = self._first_visible(
                        By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'
                    )
                    label = (primary.text or "").strip() if primary else ""
                    if label == "Next":
                        self._native_click(primary)
                WebDriverWait(self.driver, 15).until(self._recovery_next_screen_opened)
            self._sent_recovery_option = True
            return True
        except Exception as exc:
            logger.error("Ошибка при поиске резервной почты %s", _short_exception(exc))
            self.entity.error = AccessStatusError.CHECK_RECOVERY_MAIL_ERROR
            self.create_screenshot()
            return False

    def write_recovery_email(self) -> bool:
        if self._submitted_recovery_email:
            return True
        try:
            WebDriverWait(self.driver, 15).until(
                ec.element_to_be_clickable((By.ID, "proof-confirmation-email-input"))
            )
            field = self.driver.find_element(By.ID, "proof-confirmation-email-input")
            field.click()
            field = self.driver.find_element(By.ID, "proof-confirmation-email-input")
            field.clear()
            field = self.driver.find_element(By.ID, "proof-confirmation-email-input")
            field.send_keys(RECOVERY_EMAIL)
            WebDriverWait(self.driver, 5).until(
                lambda d: d.find_element(
                    By.ID, "proof-confirmation-email-input"
                ).get_attribute("value") == RECOVERY_EMAIL
            )
            send_btn = WebDriverWait(self.driver, 10).until(
                ec.element_to_be_clickable((By.XPATH,
                    "//button[@data-testid='primaryButton'][@type='submit']"
                    "[normalize-space(.)='Send code' or normalize-space(.)='Next']"))
            )
            self._native_click(send_btn)
            WebDriverWait(self.driver, 15).until(
                lambda d: bool(
                    self._could_not_send_code()
                    or self._first_visible(By.CSS_SELECTOR, "input[autocomplete='one-time-code']")
                    or self._first_visible(By.XPATH, "//*[contains(., 'Enter your code')]")
                )
            )
            if self._could_not_send_code():
                logger.warning("Microsoft не отправил код, переходим к паролю")
                self._skip_recovery = True
                return False
            self._submitted_recovery_email = True
            return True
        except Exception as exc:
            logger.error("Ошибка при вводе резервной почты %s", _short_exception(exc))
            self.entity.error = AccessStatusError.CHECK_RECOVERY_MAIL_ERROR
            self.create_screenshot()
            return False


        # try:
        #     self.driver.find_element(By.XPATH,
        #                              "//*[contains(text(), \"That doesn't match the alternate email associated with your account. The correct email starts with\")]")
        #     self.entity.error = AccessStatusError.CHECK_RECOVERY_MAIL_ERROR
        #     logger.error("Ошибка при вводе резервной почты")
        #     self.create_screenshot()
        #     raise CustomExitException
        # except Exception as exc:
        #     logger.error("Ошибка при проверке наличия ошибки: %s", _short_exception(exc))
        #     self.create_screenshot()
    
    def find_recovery_mail_code(self) -> bool:
        try:
            one_time_code_wait = self.driver.find_element(
                By.CSS_SELECTOR, "input[autocomplete='one-time-code']"
            )
            code = self.mail_service.run(from_email={
                "email": IMAP_EMAIL,
                "password": IMAP_PASS
            })
            if not code:
                return False
            one_time_code_wait.clear()
            one_time_code_wait.send_keys(code)
            primary = self._first_visible(
                By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'
            )
            if primary:
                self._native_click(primary)
            return True
        except Exception as exc:
            logger.error("Ошибка при поиске места ввода кода от резервной почты: %s", _short_exception(exc))
            self.create_screenshot()
            return False
        
    
    def incorrect_code_from_recovery_mail(self):
        try:
            self.driver.find_element(By.XPATH,
                                     "//*[contains(text(), \"That code is incorrect. Check the code and try again.\")]")
            self.entity.error = AccessStatusError.CHECK_RECOVERY_MAIL_ERROR
            logger.error("Ошибка при вводе резервной почты")
            self.create_screenshot()
            raise CustomExitException
        except Exception as exc:
            logger.error("Ошибка при проверке наличия ошибки: %s", _short_exception(exc))
            self.create_screenshot()

    def find_page(self):
        timeout = 15  # простой между сменами экрана
        max_total_time = 60  # навигация без ожидания письма
        mail_wait_timeout = 45  # ожидание кода на экране OTP
        approve_wait_timeout = 10
        start_time = time.monotonic()
        overall_start_time = start_time
        otp_wait_started = None
        approve_wait_started = None

        while True:
            now = time.monotonic()
            waiting_mail = (not self._skip_recovery) and bool(
                self._first_visible(By.CSS_SELECTOR, "input[autocomplete='one-time-code']")
            )
            waiting_approve = self._is_approve_sign_in_page()

            if waiting_mail:
                if otp_wait_started is None:
                    otp_wait_started = now
                start_time = now
                if now - otp_wait_started > mail_wait_timeout:
                    logger.info("Письмо с кодом не пришло за %s сек.", mail_wait_timeout)
                    self.entity.error = AccessStatusError.CHECK_RECOVERY_MAIL_ERROR
                    self.create_screenshot()
                    break
            elif waiting_approve:
                otp_wait_started = None
                if approve_wait_started is None:
                    approve_wait_started = now
                    logger.info("Ожидание одобрения входа %s сек", approve_wait_timeout)
                    self.entity.error = AccessStatusError.APPROVE_SIGN_IN
                    self.entity.success = AccessStatusSolution.ERROR
                    self.publisher.publish(entity=self.entity)
                start_time = now
                if now - approve_wait_started > approve_wait_timeout:
                    logger.info("Вход не одобрили за %s сек", approve_wait_timeout)
                    self.entity.error = AccessStatusError.LOGIN_NOT_COMPLETED
                    self.entity.success = AccessStatusSolution.ERROR
                    self.create_screenshot()
                    raise CustomExitException
                time.sleep(0.5)
                continue
            else:
                otp_wait_started = None
                approve_wait_started = None
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

            if self._could_not_send_code() and not self._skip_recovery:
                logger.warning("Microsoft не отправил код, переходим к паролю")
                self._skip_recovery = True
                start_time = time.monotonic()

            if not self._skip_recovery and self._first_visible(By.ID, "proof-confirmation-email-input"):
                if self.write_recovery_email():
                    start_time = time.monotonic()
                continue

            if not self._skip_recovery and self._has(*self._send_code_to_locator()):
                if self.check_recovery_mail():
                    start_time = time.monotonic()
                continue

            if not self._skip_recovery and self._recovery_options_without_our_mail():
                self._mark_missing_recovery_mail()
                self._skip_recovery = True
                start_time = time.monotonic()

            if waiting_mail:
                if self.find_recovery_mail_code():
                    start_time = time.monotonic()
                else:
                    time.sleep(2)
                continue

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

            if (
                not self._password_submitted
                and not self._first_visible(By.ID, 'passwordEntry')
                and self._first_visible(*self._other_ways_locator())
                and (self._skip_recovery or not self._other_login_clicked)
            ):
                self.check_other_login()
                self._other_login_clicked = True
                start_time = time.monotonic()
                continue

            if self._skip_recovery and self._first_visible(*self._use_password_locator()):
                if self.check_use_password():
                    start_time = time.monotonic()
                continue

            if self._is_totp_window():
                self.enter_authenticator_code()
                start_time = time.monotonic()
                continue

            try:
                self.driver.find_element(By.XPATH,
                                         "//*[contains(text(), \"Get a new code from the device you're trying to sign in to and try again\")]")
                self.check_code_expired()
                start_time = time.monotonic()
            except Exception:
                pass

            try:
                self.driver.find_element(By.XPATH,
                                         "//*[contains(text(), \"Don't recognize or have any of these\")]")
                if not self._skip_recovery:
                    self.check_2fa()
                    start_time = time.monotonic()
            except Exception:
                pass

            # try:
            #     self.driver.find_element(By.ID, 'lightbox-cover')
            #     self.check_authenticator()
            #     start_time = time.monotonic()
            # except Exception:
            #     pass

            try:
                self.driver.find_element(By.XPATH, "//h1[contains(., 'Stay signed in')]")
                self.check_stay_log_in()
                start_time = time.monotonic()
            except Exception:
                pass

            # try:
            #     self.driver.find_element(By.ID, 'iShowSkip')
            #     self.check_recovery_mail()
            #     start_time = time.monotonic()
            # except Exception:
            #     pass

            try:
                self.driver.find_element(By.ID, 'iLooksGood')
                self.security_info_accurate()
                start_time = time.monotonic()
            except Exception:
                pass

            # try:
            #     self.driver.find_element(By.CSS_SELECTOR, 'button[data-testid="primaryButton')
            #     self.check_faq_button()
            #     start_time = time.monotonic()
            # except Exception:
            #     pass

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