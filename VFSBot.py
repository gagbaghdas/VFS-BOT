import time
import threading
import undetected_chromedriver as uc
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from telegram.ext import Updater, CommandHandler
from configparser import ConfigParser
import logging
from utils import *
from selenium_recaptcha_solver import API as RecaptchaSolver
from selenium import webdriver
from selenium.webdriver.chrome.service import Service

class VFSBot:
    def __init__(self):
        self.browser = None
        self.thr = None
        self.started = False
        self.options = None
        self.driver = None
        self.logger = self.init_logger()
        self.init_config()
        self.init_telegram_bot()
       
    def init_config(self):
        config = ConfigParser()
        config.read('config.ini')
        self.url = config.get('VFS', 'url')
        self.email_str = config.get('VFS', 'email')
        self.pwd_str = config.get('VFS', 'password')
        self.interval = config.getint('DEFAULT', 'interval')
        self.channel_id = config.get('TELEGRAM', 'channel_id')
        self.token = config.get('TELEGRAM', 'auth_token')
        self.admin_ids = list(map(int, config.get('TELEGRAM', 'admin_ids').split(" ")))

    def init_telegram_bot(self):
        updater = Updater(self.token, use_context=True)
        dp = updater.dispatcher
        dp.add_handler(CommandHandler("start", self.start))
        dp.add_handler(CommandHandler("help", self.help))
        dp.add_handler(CommandHandler("quit", self.quit))
        updater.start_polling()
        updater.idle()

    def init_logger(self):
        logger = logging.getLogger('VFSBot')
        logger.setLevel(logging.INFO)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        return logger

    def login(self, update, context):
        try:
            self.browser.get(self.url)
            self.handle_login_page(update, context)
        except WebDriverException as e:
            self.logger.error(f"WebDriverException occurred: {e}")
            # Add specific recovery or retry logic here if needed
        except TimeoutException as e:
            self.logger.error(f"TimeoutException occurred: {e}")
            # Add specific recovery or retry logic here if needed
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
            # Handle other exceptions or add recovery logic

    def handle_login_page(self, update, context):
        if "Enter your email and password to continue" not in self.browser.page_source:
            self.process_credentials(update, context)
        elif "Your account has been locked" in self.browser.page_source:
            self.handle_account_lock(update)
        elif "The verification words are incorrect" in self.browser.page_source:
            # Handle incorrect captcha
            pass
        elif "You are being rate limited" in self.browser.page_source:
            self.handle_rate_limiting(update)
        else:
            update.message.reply_text("An unknown error has occurred. \nTrying again.")
            raise WebError
    
    def process_credentials(self, update, context):
        update.message.reply_text("You are now in queue.")
        WebDriverWait(self.browser, 10).until(
            EC.presence_of_element_located((By.ID, 'mat-input-0'))
        )

        self.browser.find_element(by=By.ID, value='mat-input-0').send_keys(self.email_str)
        self.browser.find_element(by=By.ID, value='mat-input-1').send_keys(self.pwd_str)

        self.solve_captcha()
        # self.browser.find_element(by=By.NAME, value='CaptchaInputText').send_keys(captcha)
        # self.browser.find_element(by=By.ID, value='btnSubmit').click()

        # if "Reschedule Appointment" in self.browser.page_source:
        self.post_login_success(update, context)

    def solve_captcha(self):
        # update.message.reply_text("Sending Captcha...")
        solver = RecaptchaSolver(driver=self.browser)
        recaptcha_iframe = self.browser.find_element(By.XPATH, '//iframe[@title="reCAPTCHA"]')
        solver.click_recaptcha_v2(iframe=recaptcha_iframe)


        # captcha_img = self.browser.find_element(by=By.ID, value='rc-imageselect')
                
        # self.captcha_filename = 'captcha.png'
        # with open(self.captcha_filename, 'wb') as file:
        #     file.write(captcha_img.screenshot_as_png)

        # captcha = break_captcha()
        pass

    def post_login_success(self, update, context):
        update.message.reply_text("Successfully logged in!")
        while True:
            try:
                self.check_appointment(update, context)
            except WebError:
                update.message.reply_text("An WebError has occured.\nTrying again.")
                raise WebError
            except Offline:
                update.message.reply_text("Downloaded offline version. \nTrying again.")
                continue
            except Exception as e:
                update.message.reply_text("An error has occured: " + e + "\nTrying again.")
                raise WebError
            time.sleep(self.interval)

    def handle_account_lock(self, update):
        update.message.reply_text("Account locked.\nPlease wait 2 minutes.")
        time.sleep(120)

    def handle_rate_limiting(self, update):
        update.message.reply_text("Rate Limited. \nPlease wait 5 minutes.")
        time.sleep(300)

    def login_helper(self, update, context):
        self.browser = self.driver  
        while self.started:
            try:
                self.login(update, context)
            except Exception as e:
                self.logger.error(f"Error in login_helper: {e}")
                continue
                
    def help(self, update, context):
        update.message.reply_text("This is a VFS appointment bot!\nPress /start to begin.")

    def start(self, update, context):


        service = Service()
        self.options = webdriver.ChromeOptions()
        self.options.add_argument('--disable-gpu')

        self.driver = webdriver.Chrome(service=service, options=self.options)
        # self.options = uc.ChromeOptions()
        #Uncomment the following line to run headless
        #self.options.add_argument('--headless=new')
        
        if self.thr and self.thr.is_alive():
            update.message.reply_text("Bot is already running.")
            return
        self.thr = threading.Thread(target=self.login_helper, args=(update, context))  
        self.thr.start()
        self.started = True

    
    def quit(self, update, context):
        if not self.started:
            update.message.reply_text("Cannot quit. Bot is not running.")
            return
        try:
            self.browser.quit()
        except Exception as e:
            update.message.reply_text("Quit unsuccessful.")
            self.logger.error(f"Error during quitting: {e}")
            return
        self.thr = None
        self.started = False
        update.message.reply_text("Quit successfully.")
        
    
    def check_errors(self):
        if "Server Error in '/Global-Appointment' Application." in self.browser.page_source:
            return True
        elif "Cloudflare" in self.browser.page_source:
            return True
        elif "Sorry, looks like you were going too fast." in self.browser.page_source:
            return True
        elif "Session expired." in self.browser.page_source:
            return True
        elif "Sorry, looks like you were going too fast." in self.browser.page_source:
            return True
        elif "Sorry, Something has gone" in self.browser.page_source:
            return True
        
    def check_offline(self):
        if "offline" in self.browser.page_source:
            return True
            
    def check_appointment(self, update, context):
        time.sleep(5)
    
        self.browser.find_element(by=By.XPATH, 
                                value='//*[@id="Accordion1"]/div/div[2]/div/ul/li[1]/a').click()
        if self.check_errors():
            raise WebError
        if self.check_offline():
            raise Offline
    
        WebDriverWait(self.browser, 100).until(EC.presence_of_element_located((
            By.XPATH, '//*[@id="LocationId"]')))
        
        self.browser.find_element(by=By.XPATH, value='//*[@id="LocationId"]').click()
        if self.check_errors():
             raise WebError
        time.sleep(3)
    
            
        self.browser.find_element(by=By.XPATH, value='//*[@id="LocationId"]/option[2]').click()
        if self.check_errors():
            raise WebError
    
        time.sleep(3)

            
        if "There are no open seats available for selected center - Belgium Long Term Visa Application Center-Tehran" in self.browser.page_source:
            #update.message.reply_text("There are no appointments available.")
            records = open("record.txt", "r+")
            last_date = records.readlines()[-1]
            
            if last_date != '0':
                context.bot.send_message(chat_id=self.channel_id,
                                         text="There are no appointments available right now.")
                records.write('\n' + '0')
                records.close
        else:
            select = Select(self.browser.find_element(by=By.XPATH, value='//*[@id="VisaCategoryId"]'))
            select.select_by_value('1314')
            
            WebDriverWait(self.browser, 100).until(EC.presence_of_element_located((
                By.XPATH, '//*[@id="dvEarliestDateLnk"]')))
    
            time.sleep(2)
            new_date = self.browser.find_element(by=By.XPATH, 
                           value='//*[@id="lblDate"]').get_attribute('innerHTML')
            
            records = open("record.txt", "r+")
            last_date = records.readlines()[-1]

            if new_date != last_date and len(new_date) > 0:
                context.bot.send_message(chat_id=self.channel_id,
                                         text=f"Appointment available on {new_date}.")
                records.write('\n' + new_date)
                records.close()
        #Uncomment if you want the bot to notify everytime it checks appointments.
        #update.message.reply_text("Checked!", disable_notification=True)
        return True

if __name__ == '__main__':
    VFSbot = VFSBot()
