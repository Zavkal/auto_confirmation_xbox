import copy
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
        # self.options.add_argument('--headless')
        self.driver = webdriver.Chrome(options=self.options)


    def confirmation_code(self, data: dict):
        error_data = copy.deepcopy(data)
        code = data['code']
        email = data['login']
        password = data['password']
        print(data, email, password)

        self.driver.get('https://login.live.com/oauth20_remoteconnect.srf')

        try:
            self.driver.find_element(By.ID, 'otc').send_keys(code) # Кнопка ввода кода
            self.driver.find_element(By.ID, 'idSIButton9').click()
            try:
                email_text = WebDriverWait(self.driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'i0116'))
                )
                email_text.click()
                email_text.send_keys(email) # Кнопка ввода email
                self.driver.find_element(By.ID, 'idSIButton9').click() # - Версия Димы

                password_text = WebDriverWait(self.driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'i0118'))
                )  # Кнопка ввода пароля
                password_text.click()
                password_text.send_keys(password)
                self.driver.find_element(By.ID, 'idSIButton9').click() # - Версия Димы
                try:
                    WebDriverWait(self.driver, 5).until(
                        ec.presence_of_element_located(
                            (By.ID, 'declineButton'))).click()  # Кнопка "нет" при запросе остаться в системе
                    data['success'] = 'True'
                    data['error'] = 0
                    send_result_message(data)
                    self.driver.quit()
                    return
                except TimeoutException:
                    pass

                try:
                    while True:
                        WebDriverWait(self.driver, 5).until(
                            ec.presence_of_element_located((By.ID,
                                                            'iLooksGood'))).click()  # - После аутентификатора просит подтвердить. Сделать проверку нахождения такой кнопки (Она может быть циклична)
                except Exception:
                    pass

                try:
                    WebDriverWait(self.driver, 5).until(
                        ec.presence_of_element_located((By.ID, 'inner')))  # - Запрос аутентификатора после ввода пароля
                    error_data['error'] = 2
                    error_data['success'] = 'False'
                    send_result_message(error_data)
                    self.driver.quit()
                    return

                except Exception:
                    pass

                WebDriverWait(self.driver, 5).until(
                    ec.presence_of_element_located(
                        (By.ID, 'declineButton'))).click()  # Кнопка "нет" при запросе остаться в системе
                data['success'] = 'True'
                data['error'] = 0
                send_result_message(data)
                self.driver.quit()
                self.driver.quit()


            except Exception as e:
                print(e)
                email_text = WebDriverWait(self.driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'usernameEntry'))
                )
                email_text.click()
                email_text.send_keys(email) # Кнопка ввода email
                WebDriverWait(self.driver, 5).until(
                    ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
                ).click() # - Версия Сани
                try:
                    WebDriverWait(self.driver, 3).until(
                        ec.presence_of_element_located((By.ID, 'idA_PWD_SwitchToPassword'))
                    ).click()
                except Exception:
                    pass
                password_text = WebDriverWait(self.driver, 5).until(
                    ec.presence_of_element_located((By.ID, 'passwordEntry')))  # Кнопка ввода пароля
                password_text.click()
                password_text.send_keys(password)
                WebDriverWait(self.driver, 5).until(
                    ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="primaryButton"]'))
                ).click() # - Версия Сани
                try:
                    WebDriverWait(self.driver, 5).until(
                        ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
                    ).click()  # - Кнопка остаться в системе
                    data['success'] = 'True'
                    data['error'] = 0
                    send_result_message(data)
                    self.driver.quit()
                    return
                except Exception:
                    pass

                try:
                    while True:
                        WebDriverWait(self.driver, 5).until(
                            ec.element_to_be_clickable(
                                (By.ID, 'iShowSkip'))).click() # После ввода пароля просит резерв почту

                except Exception:
                    pass
                try:
                    WebDriverWait(self.driver, 5).until(
                        ec.element_to_be_clickable(
                            (By.ID, 'lightbox-cover'))).click()  # Просит аутентификацию
                except Exception:
                    error_data['error'] = 2
                    error_data['success'] = 'False'
                    send_result_message(error_data)
                    self.driver.quit()
                    return

                try:
                    WebDriverWait(self.driver, 5).until(
                        ec.element_to_be_clickable((By.CSS_SELECTOR, 'button[data-testid="secondaryButton"]'))
                    ).click()  # - Кнопка остаться в системе
                    data['success'] = 'True'
                    data['error'] = 0
                    send_result_message(data)
                    self.driver.quit()


                except TimeoutException:
                    error_data['error'] = 2
                    error_data['success'] = 'False'
                    send_result_message(error_data)
                    self.driver.quit()
                    return


        except Exception as e:
            print(e)
            error_data['error'] = 1
            error_data['success'] = 'False'
            send_result_message(error_data)
            self.driver.quit()
            return





