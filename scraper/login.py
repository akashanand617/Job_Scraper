#!/usr/bin/env python3
"""
Simple LinkedIn login script.
"""

from linkedin_scraper import login_and_save_cookies
from fake_useragent import UserAgent
from getpass import getpass
import os
from dotenv import load_dotenv

load_dotenv()

def main():
    print("🔐 LinkedIn Login")
    
    # Get credentials
    email = os.getenv('LINKEDIN_EMAIL')
    password = os.getenv('LINKEDIN_PASSWORD')
    
    if not email or not password:
        email = input("Email: ")
        password = getpass("Password: ")
    
    # Login with default User Agent (custom UA causes crashes)
    print("Using default User Agent...")
    try:
        login_and_save_cookies(email, password)
        print("✅ Login successful!")
    except Exception as e:
        print(f"❌ Login failed: {e}")

if __name__ == "__main__":
    main() 