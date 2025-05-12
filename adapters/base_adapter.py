import copy
import tempfile
import time

from selenium import webdriver
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by   import By
from selenium.webdriver.support     import expected_conditions as ec
from selenium.webdriver.chrome.options import Options as ChromeOptions
from seleniumbase.common.exceptions import TimeoutException

from rabbit.send_result import send_result_message


class SeleniumConfirmation:
    def __init__(self):
        self.options = ChromeOptions()
        self.options.add_argument('--incognito')
        self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')

        tmp_profile_dir = tempfile.mkdtemp()
        self.options.add_argument(f'--user-data-dir={tmp_profile_dir}')
        self.driver = webdriver.Chrome(options=self.options)



    def confirmation_code(self, data: dict):
        error_data = copy.deepcopy(data)
        code = data['code']
        email = data['login']
        password = data['password']
        data['success'] = 'False'
        data['error'] = 10
        send_result_message(data)

        self.driver.get('https://login.live.com/oauth20_remoteconnect.srf')
        self.driver.find_element(By.ID, 'otc').send_keys(code)  # Кнопка ввода кода
        self.driver.find_element(By.ID, 'idSIButton9').click()
        time.sleep(10)

        try:
            self.new_site(driver=self.driver,
                          data=data,
                          email=email,
                          password=password,
                          error_data=error_data
                          )
        except Exception as e:
            try:
                self.old_site(driver=self.driver,
                              data=data,
                              email=email,
                              password=password,
                              error_data=error_data)
            except Exception as e:
                error_data['error'] = 9
                error_data['success'] = 'False'
                send_result_message(data)
        finally:
            self.driver.quit()

    @staticmethod
    def new_site(driver, data: dict, email: str, password: str, error_data: dict):
        try:
            email_text = WebDriverWait(driver, 5).until(
                ec.presence_of_element_located((By.ID, 'usernameEntry'))
            )
            email_text.click()
            email_text.send_keys(email) # Кнопка ввода email

            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
            ).click()
        except Exception: # Отправляем ошибку о том, что код не верный
            error_data['error'] = 1
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return
        try:
            driver.find_element(By.ID, "error")
            error_data['error'] = 1
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return
        except Exception:
            pass

        try:
            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.XPATH, "//span[@role='button' and text()='Use your password']"))
            ).click()
        except Exception:
            pass
        try:
            WebDriverWait(driver, 3).until(
                ec.presence_of_element_located((By.XPATH, "//span[@role='button' and text()='Use your password']"))
            ).click()
        except Exception:
            pass
        try:
            WebDriverWait(driver, 3).until(
                ec.presence_of_element_located((By.ID, 'fui-CardHeader__header30'))
            ).click()
        except Exception:
            pass
        try:
            WebDriverWait(driver, 3).until(
                ec.presence_of_element_located((By.ID, 'idA_PWD_SwitchToPassword'))
            ).click()
        except Exception:
            pass

        password_text = WebDriverWait(driver, 5).until(
            ec.presence_of_element_located((By.ID, 'passwordEntry')))  # Кнопка ввода пароля
        password_text.click()
        password_text.send_keys(password)
        WebDriverWait(driver, 5).until(
            ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
        ).click()

        try:
            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
            ).click()  # - Кнопка остаться в системе
            data['success'] = 'True'
            data['error'] = 0
            send_result_message(data)
            driver.quit()
            return
        except Exception:
            pass

        try:
            while True:
                WebDriverWait(driver, 5).until(
                    ec.element_to_be_clickable(
                        (By.ID, 'iShowSkip'))).click() # После ввода пароля просит резерв почту

        except Exception:
            pass
        try:
            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable(
                    (By.ID, 'lightbox-cover'))).click()  # Просит аутентификацию
        except Exception as e:
            print(e)
            error_data['error'] = 2
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return

        try:
            WebDriverWait(driver, 5).until(
                ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
            ).click()  # - Кнопка остаться в системе
            data['success'] = 'True'
            data['error'] = 0
            send_result_message(data)
            driver.quit()
            return


        except Exception as e:
            print(e)
            error_data['error'] = 2
            error_data['success'] = 'False'
            send_result_message(error_data)
            driver.quit()
            return


        error_data['error'] = 9
        error_data['success'] = 'False'
        send_result_message(error_data)
        self.driver.quit()
        return


    @staticmethod
    def old_site(driver, data: dict, email: str, password: str, error_data: dict) -> None:
        try:
            email_text = WebDriverWait(driver, 5).until(
                ec.presence_of_element_located((By.ID, 'i0116'))
            )
            email_text.click()
            email_text.send_keys(email) # Кнопка ввода email
            driver.find_element(By.ID, 'idSIButton9').click() # - Версия Димы
            try:
                password_text = WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'i0118'))
                )  # Кнопка ввода пароля
                password_text.click()
                password_text.send_keys(password)
                driver.find_element(By.ID, 'idSIButton9').click() # - Версия Димы
            except Exception:
                data['success'] = 'False'
                data['error'] = 3
                send_result_message(data)
                driver.quit()
                return
            try:
                WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located(
                        (By.ID, 'declineButton'))).click()  # Кнопка "нет" при запросе остаться в системе
                data['success'] = 'True'
                data['error'] = 0
                send_result_message(data)
                driver.quit()
                return
            except TimeoutException:
                pass

            try:
                while True:
                    WebDriverWait(driver, 5).until(
                        ec.presence_of_element_located((By.ID,
                                                        'iLooksGood'))).click()  # - После аутентификатора просит подтвердить. Сделать проверку нахождения такой кнопки (Она может быть циклична)
            except Exception:
                pass

            try:
                WebDriverWait(driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'inner')))  # - Запрос аутентификатора после ввода пароля
                error_data['error'] = 2
                error_data['success'] = 'False'
                send_result_message(error_data)
                driver.quit()
                return

            except Exception:
                pass

            WebDriverWait(driver, 5).until(
                ec.presence_of_element_located(
                    (By.ID, 'secondaryButton'))).click()  # Кнопка "нет" при запросе остаться в системе
            data['success'] = 'True'
            data['error'] = 0
            send_result_message(data)
            driver.quit()
            return

        except Exception:
            error_data['error'] = 9
            error_data['success'] = 'False'
            send_result_message(data)
            driver.quit()
            return



if __name__ == '__main__':
    SeleniumConfirmation().confirmation_code(data={'code': 'UQWY7CU2', 'user_id': 1463186913, 'product_id': '281', 'order_id': 1414, 'login': 'Dl2privat2@ya.ru', 'password': 'box22222', 'user_message_id': 29046, 'product_title': 'Dying Light 2 - Ultimate', 'back_from': 'delivery', 'subs_period_id': None, 'error': 9, 'success': 'False'})
