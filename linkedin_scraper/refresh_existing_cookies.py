#!/usr/bin/env python3
"""
Refresh existing LinkedIn cookies by visiting LinkedIn with current cookies
This approach is less likely to trigger 2FA than a full login
"""

import undetected_chromedriver as uc
import pickle
import time
import os
import boto3
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

load_dotenv()

def refresh_existing_cookies():
    """Refresh existing cookies by visiting LinkedIn"""
    print("🍪 Refreshing existing LinkedIn cookies...")
    
    # Setup browser options
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
    else:
        # Local macOS environment - use more conservative options
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-extensions')
        options.add_argument('--no-first-run')
        options.add_argument('--disable-default-apps')
    
    # Create driver
    driver = uc.Chrome(options=options)
    
    try:
        # First, try to load existing cookies from S3
        cookies_loaded = False
        try:
            bucket_name = os.getenv('JOBS_BUCKET', 'linkedin-job-scraper-dev-jobs')
            s3_client = boto3.client('s3')
            s3_key = "cookies/li_cookies.pkl"
            
            # Download cookies from S3
            s3_client.download_file(bucket_name, s3_key, 'li_cookies.pkl')
            print("✅ Downloaded existing cookies from S3")
            cookies_loaded = True
        except Exception as e:
            print(f"⚠️ Could not download cookies from S3: {e}")
            # Try local file
            if os.path.exists('li_cookies.pkl'):
                print("✅ Using local cookies file")
                cookies_loaded = True
        
        if not cookies_loaded:
            print("❌ No existing cookies found. Please run full login first.")
            return False
        
        # Load cookies
        with open('li_cookies.pkl', 'rb') as f:
            cookies = pickle.load(f)
        
        print(f"📦 Loaded {len(cookies)} existing cookies")
        
        # Go to LinkedIn first (before adding cookies)
        driver.get('https://www.linkedin.com')
        time.sleep(2)
        
        # Add cookies to the browser
        for cookie in cookies:
            try:
                # Remove domain restrictions for cookie compatibility
                cookie_dict = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', False),
                    'httpOnly': cookie.get('httpOnly', False)
                }
                
                # Only add domain if it's not a wildcard
                if 'domain' in cookie and not cookie['domain'].startswith('.'):
                    cookie_dict['domain'] = cookie['domain']
                
                driver.add_cookie(cookie_dict)
            except Exception as e:
                print(f"⚠️ Could not add cookie {cookie.get('name', 'unknown')}: {e}")
        
        print("🍪 Cookies added to browser")
        
        # Refresh the page to apply cookies
        driver.refresh()
        time.sleep(3)
        
        # Check if we're logged in by looking for LinkedIn feed elements
        try:
            WebDriverWait(driver, 10).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-test-id='search-input']")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".global-nav__me")),
                    EC.url_contains("linkedin.com/feed")
                )
            )
            print("✅ Successfully refreshed cookies - still logged in!")
            
            # Get updated cookies
            updated_cookies = driver.get_cookies()
            
            # Save updated cookies
            with open('li_cookies.pkl', 'wb') as f:
                pickle.dump(updated_cookies, f)
            
            print(f"💾 Updated cookies saved ({len(updated_cookies)} cookies)")
            
            # Upload to S3
            bucket_name = os.getenv('JOBS_BUCKET', 'linkedin-job-scraper-dev-jobs')
            s3_key = "cookies/li_cookies.pkl"
            
            s3_client = boto3.client('s3')
            s3_client.upload_file('li_cookies.pkl', bucket_name, s3_key)
            print(f"✅ Updated cookies uploaded to s3://{bucket_name}/{s3_key}")
            
            # Upload metadata
            metadata = {
                "refreshed_at": datetime.now(timezone.utc).isoformat(),
                "bucket": bucket_name,
                "key": s3_key,
                "status": "success",
                "method": "cookie_refresh"
            }
            
            metadata_key = "cookies/li_cookies_metadata.json"
            s3_client.put_object(
                Bucket=bucket_name,
                Key=metadata_key,
                Body=json.dumps(metadata, indent=2),
                ContentType='application/json'
            )
            
            print("✅ Cookie refresh completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Cookie refresh failed: {e}")
            print(f"Current URL: {driver.current_url}")
            
            # Check if we're on a login page
            if "login" in driver.current_url or "challenge" in driver.current_url:
                print("🔐 Cookies expired - full login required")
                return False
            else:
                print("⚠️ Unknown error during cookie refresh")
                return False
                
    except Exception as e:
        print(f"❌ Error during cookie refresh: {e}")
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = refresh_existing_cookies()
    exit(0 if success else 1)
