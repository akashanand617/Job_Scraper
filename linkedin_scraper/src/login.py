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
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--headless')  # Run headless in CI
    
    # Create driver
    driver = uc.Chrome(options=options)
    
    try:
        # Go to LinkedIn login
        driver.get('https://www.linkedin.com/login')
        
        # Wait for login form and enter credentials
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        password_field = driver.find_element(By.ID, "password")
        
        email_field.send_keys(email)
        password_field.send_keys(password)
        
        # Click login button
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        # Wait for successful login
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']"))
        )
        
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