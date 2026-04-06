#!/usr/bin/env python3
"""
Refresh existing LinkedIn cookies by visiting LinkedIn with current cookies.
Two strategies:
  1. HTTP-only refresh (fast, no browser needed) — uses requests to hit LinkedIn
     with existing cookies, which extends the session server-side.
  2. Browser refresh (fallback) — opens headless Chrome with cookies loaded.
"""

import pickle
import time
import os
import re
import subprocess
import boto3
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()


def load_cookies_from_s3():
    """Download cookies from S3, falling back to local file. Returns list or None."""
    bucket_name = os.getenv('JOBS_BUCKET', 'linkedin-job-scraper-dev-jobs')
    s3_client = boto3.client('s3')
    s3_key = "cookies/li_cookies.pkl"

    try:
        s3_client.download_file(bucket_name, s3_key, 'li_cookies.pkl')
        print("✅ Downloaded existing cookies from S3")
    except Exception as e:
        print(f"⚠️ Could not download cookies from S3: {e}")
        if not os.path.exists('li_cookies.pkl'):
            print("❌ No existing cookies found. Please run full login first.")
            return None
        print("✅ Using local cookies file")

    with open('li_cookies.pkl', 'rb') as f:
        cookies = pickle.load(f)
    print(f"📦 Loaded {len(cookies)} existing cookies")
    return cookies


def upload_cookies_to_s3(method="cookie_refresh"):
    """Upload li_cookies.pkl and metadata to S3."""
    bucket_name = os.getenv('JOBS_BUCKET', 'linkedin-job-scraper-dev-jobs')
    s3_client = boto3.client('s3')
    s3_key = "cookies/li_cookies.pkl"

    s3_client.upload_file('li_cookies.pkl', bucket_name, s3_key)
    print(f"✅ Updated cookies uploaded to s3://{bucket_name}/{s3_key}")

    metadata = {
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "bucket": bucket_name,
        "key": s3_key,
        "status": "success",
        "method": method,
    }
    s3_client.put_object(
        Bucket=bucket_name,
        Key="cookies/li_cookies_metadata.json",
        Body=json.dumps(metadata, indent=2),
        ContentType='application/json',
    )


# ---------------------------------------------------------------------------
# Strategy 1: HTTP-only refresh (no browser)
# ---------------------------------------------------------------------------

def refresh_via_http(cookies):
    """
    Hit LinkedIn with existing cookies via requests.
    If the session is still valid, LinkedIn returns a 200 on the feed and
    sends back updated Set-Cookie headers that extend the session.
    """
    print("\n🌐 Attempting HTTP-only cookie refresh...")

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                       '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })

    # Load cookies into the requests session
    for c in cookies:
        session.cookies.set(
            c['name'],
            c['value'],
            domain=c.get('domain', '.linkedin.com'),
            path=c.get('path', '/'),
        )

    # Hit the feed — if session is valid this returns 200 and refreshes cookies
    resp = session.get('https://www.linkedin.com/feed/', allow_redirects=True, timeout=30)

    # Check if we landed on the feed (logged in) vs login/auth wall
    if resp.status_code == 200 and '/feed' in resp.url and 'login' not in resp.url:
        print(f"✅ HTTP refresh succeeded (landed on {resp.url})")

        # Merge updated cookies back into the original cookie list
        updated = []
        seen = set()
        # Prefer cookies from the response (they have fresh expiry)
        for c in session.cookies:
            updated.append({
                'name': c.name,
                'value': c.value,
                'domain': c.domain,
                'path': c.path,
                'secure': c.secure,
                'httpOnly': False,  # requests doesn't track this
            })
            seen.add(c.name)
        # Keep original cookies that weren't replaced (preserves httpOnly flag etc.)
        for c in cookies:
            if c['name'] not in seen:
                updated.append(c)

        with open('li_cookies.pkl', 'wb') as f:
            pickle.dump(updated, f)
        print(f"💾 Saved {len(updated)} refreshed cookies")

        upload_cookies_to_s3(method="http_refresh")
        print("✅ HTTP cookie refresh completed successfully!")
        return True

    print(f"❌ HTTP refresh failed — status {resp.status_code}, url {resp.url}")
    return False


# ---------------------------------------------------------------------------
# Strategy 2: Browser refresh (fallback)
# ---------------------------------------------------------------------------

def detect_chrome_version():
    """Detect the installed Chrome/Chromium major version."""
    candidates = [
        "google-chrome --version",
        "google-chrome-stable --version",
        "chromium --version",
        "chromium-browser --version",
        '"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --version',
    ]
    for cmd in candidates:
        try:
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode()
            match = re.search(r"(\d+)\.", output)
            if match:
                version = int(match.group(1))
                print(f"🔍 Detected Chrome/Chromium version: {version}")
                return version
        except (subprocess.CalledProcessError, FileNotFoundError):
            continue
    print("⚠️ Could not detect Chrome version, letting undetected_chromedriver auto-detect")
    return None


def refresh_via_browser(cookies):
    """Load cookies into a headless browser, visit LinkedIn, and save refreshed cookies."""
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    print("\n🌐 Attempting browser-based cookie refresh...")

    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-extensions')

    if os.path.exists('/.dockerenv') or os.getenv('GITHUB_ACTIONS'):
        for path in ['/usr/bin/google-chrome-stable', '/usr/bin/google-chrome',
                      '/usr/bin/chromium-browser', '/usr/bin/chromium']:
            if os.path.exists(path):
                options.binary_location = path
                break
        options.add_argument('--headless')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (X11; Linux x86_64) '
                             'AppleWebKit/537.36 (KHTML, like Gecko) '
                             'Chrome/120.0.0.0 Safari/537.36')

    chrome_version = detect_chrome_version()
    driver = uc.Chrome(options=options, version_main=chrome_version)

    try:
        # Navigate to LinkedIn first (required before adding cookies)
        driver.get('https://www.linkedin.com')
        time.sleep(2)

        # Add cookies — include the domain even for wildcard domains
        for cookie in cookies:
            try:
                cookie_dict = {
                    'name': cookie['name'],
                    'value': cookie['value'],
                    'path': cookie.get('path', '/'),
                    'secure': cookie.get('secure', False),
                    'httpOnly': cookie.get('httpOnly', False),
                }
                if 'domain' in cookie:
                    cookie_dict['domain'] = cookie['domain']
                driver.add_cookie(cookie_dict)
            except Exception:
                pass  # some cookies legitimately can't be set cross-domain

        print("🍪 Cookies added to browser")
        driver.get('https://www.linkedin.com/feed/')
        time.sleep(5)

        # Check login state
        try:
            WebDriverWait(driver, 15).until(
                EC.any_of(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".global-nav__me")),
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input[placeholder*='Search']")),
                    EC.url_contains("linkedin.com/feed"),
                )
            )
        except Exception:
            print(f"❌ Browser refresh failed — landed on {driver.current_url}")
            return False

        print("✅ Browser refresh succeeded — still logged in!")
        updated_cookies = driver.get_cookies()

        with open('li_cookies.pkl', 'wb') as f:
            pickle.dump(updated_cookies, f)
        print(f"💾 Saved {len(updated_cookies)} refreshed cookies")

        upload_cookies_to_s3(method="browser_refresh")
        print("✅ Browser cookie refresh completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Browser refresh error: {e}")
        return False
    finally:
        driver.quit()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cookies = load_cookies_from_s3()
    if cookies is None:
        exit(1)

    # Try HTTP first (fast, no Chrome needed), fall back to browser
    if refresh_via_http(cookies):
        exit(0)

    if refresh_via_browser(cookies):
        exit(0)

    print("❌ All refresh strategies failed. Manual login required.")
    exit(1)
