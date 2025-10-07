#!/usr/bin/env python3
"""
Simple LinkedIn login script.
"""

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pickle
import time
from getpass import getpass
import os
from dotenv import load_dotenv

load_dotenv()

def login_and_save_cookies(email, password):
    """Login to LinkedIn and save cookies"""
    print("🔐 Logging into LinkedIn...")
    
    # Setup browser with optimized options (same as scraper)
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-images')
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-browser-side-navigation')
    options.add_argument('--disable-site-isolation-trials')
    options.add_argument('--disable-web-security')
    options.add_argument('--disable-features=VizDisplayCompositor')
    
    # Check if we're in Docker or GitHub Actions (use Chromium)
    if os.path.exists('/.dockerenv') or os.getenv('GITHUB_ACTIONS'):
        options.binary_location = '/usr/bin/chromium'
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-plugins')
        options.add_argument('--disable-images')
        options.add_argument('--disable-web-security')
        options.add_argument('--disable-features=VizDisplayCompositor')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Create driver with retry logic
    max_retries = 3
    for attempt in range(max_retries):
        try:
            print(f"🔄 Attempt {attempt + 1}/{max_retries} to create browser...")
            driver = uc.Chrome(options=options)
            break
        except Exception as e:
            print(f"⚠️ Browser creation attempt {attempt + 1} failed: {e}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2)
    
    try:
        # Go to LinkedIn login
        driver.get('https://www.linkedin.com/login')
        
        # Wait a bit to appear more human-like
        time.sleep(2)
        
        # Wait for login form and enter credentials
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        password_field = driver.find_element(By.ID, "password")
        
        # Type more human-like (with delays)
        for char in email:
            email_field.send_keys(char)
            time.sleep(0.1)
        
        time.sleep(1)
        
        for char in password:
            password_field.send_keys(char)
            time.sleep(0.1)
        
        time.sleep(2)
        
        # Click login button
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        time.sleep(30)
        
        # Wait for successful login (with multiple possible success indicators)
        try:
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test-id='search-input']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".global-nav__me")),
                    EC.url_contains("linkedin.com/feed")
                )
            )
        except Exception as e:
            print(f"⚠️ Login verification failed: {e}")
            # Check if we're on a 2FA page
            if "challenge" in driver.current_url or "two-factor" in driver.current_url:
                print("🔐 2FA detected - manual intervention may be required")
                raise Exception("2FA challenge detected - cannot proceed automatically")
            raise
        
        print("✅ Login successful!")
        
        # Save cookies
        cookies = driver.get_cookies()
        with open('li_cookies.pkl', 'wb') as f:
            pickle.dump(cookies, f)
        
        print("💾 Cookies saved to li_cookies.pkl")
        
    except Exception as e:
        print(f"❌ Login failed: {e}")
        raise
    finally:
        driver.quit()

def main():
    print("🔐 LinkedIn Login")
    
    # Get credentials
    email = os.getenv('LINKEDIN_EMAIL')
    password = os.getenv('LINKEDIN_PASSWORD')
    
    if not email or not password:
        email = input("Email: ")
        password = getpass("Password: ")
    
    # Login and save cookies
    try:
        login_and_save_cookies(email, password)
        print("✅ Login successful!")
    except Exception as e:
        print(f"❌ Login failed: {e}")

if __name__ == "__main__":
    main() 