#!/usr/bin/env python3
"""
Company Scraper - Collect company lists from various sources
"""

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import time
from fake_useragent import UserAgent
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv('../linkedin_scraper/.env')

def get_cb_insights():
    """Get CB Insights AI 100 2025 and Fintech 100 2024 companies"""
    
    companies_2025 = [
        "Ambience", "Apptronik", "Arcee", "Archetype AI", "Arize", "Atropos Health",
        "Binarly", "Bland AI", "Braintrust", "Browserbase", "Cartesia", "Chainguard",
        "Chroma", "Credo AI", "DEFCON AI", "ElevenLabs", "Ellipsis Health", "Etched",
        "EvolutionaryScale", "Exokernel", "Ferrum Health", "Fiddler", "Fixie",
        "Ganymede", "Hebbia", "Inflection", "K Health", "KEF Robotics", "Kumo",
        "LangChain", "Lamini", "LassoMD", "Metaplane", "Moonhub", "MotherDuck",
        "Motional", "Nomic", "OctoAI", "OneSchema", "OpenPipe", "Orby AI",
        "Perplexity", "Phind", "Pixis", "Predibase", "Primer", "Runway",
        "Seek AI", "Shaped", "Skyflow", "Snyk", "Spate", "Tavus",
        "Twelve Labs", "Together AI", "Unstructured", "Xscape Photonics", "aiXplain"
    ]

    companies_2024 = [
        "AccessFintech", "Airbase", "Alloy", "AlphaSense", "Altruist", "Arc Technologies",
        "BitGo", "Brex", "Brightside", "Clear Street", "Clerkie", "Column",
        "Dave", "Elavon", "Etana Custody", "Fattmerchant", "FinLync", "Fleetcor",
        "Highnote", "Hippo", "Imprint", "Ladder", "Lendio", "Marqeta",
        "Maverick Payments", "Next Insurance", "Oportun", "Payoneer", "Ramp",
        "Sardine", "Stripe", "Upgrade"
    ]

    
    # Combine both lists and remove duplicates
    all_companies = set(companies_2025 + companies_2024)
    
    return all_companies

def get_forbes_ai50():
    """Get Forbes AI 50 companies"""
    url = 'https://www.forbes.com/lists/ai50/'
    
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find company name elements with correct class
    company_elements = soup.find_all('div', class_='row-cell-value nameField')
    
    companies = set()
    for element in company_elements:
        company_name = element.text.strip()
        if company_name:
            companies.add(company_name)
    return companies
    
    
def get_yc_companies():
    """Get YC companies from their website"""
    url = 'https://www.ycombinator.com/companies/industry/time-series'
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for company names using the correct selector
        # Based on the search results, companies are in spans with class="text-2xl"
        company_elements = soup.find_all('span', class_='text-2xl')
        
        companies = []
        for element in company_elements:
            company_name = element.text.strip()
            if company_name:
                companies.append(company_name)
        
        print(f"✅ Found {len(companies)} YC companies")
        return companies
        
    except Exception as e:
        print(f"❌ Error scraping YC companies: {e}")
        return []
def get_glassdoor_companies():
    import undetected_chromedriver as uc
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains
    import os
    
    # Use a fixed User-Agent instead of UserAgent library
    header = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    job_titles = [
    "Research+Scientist",
    "Machine+Learning+Engineer",
    "AI+Engineer",
    "Applied+Scientist",
    ]
    
    companies = set()
    print("🏢 Starting Glassdoor scraping...")
    
    # Check for Glassdoor credentials
    glassdoor_email = os.getenv('GLASSDOOR_EMAIL')
    glassdoor_password = os.getenv('GLASSDOOR_PASSWORD')
    
    print(f"🔍 Email from env: {glassdoor_email}")
    print(f"🔍 Password from env: {'*' * len(glassdoor_password) if glassdoor_password else 'None'}")
    
    if not glassdoor_email or not glassdoor_password:
        print("❌ Glassdoor credentials not found in environment variables")
        print("   Please set GLASSDOOR_EMAIL and GLASSDOOR_PASSWORD in your .env file")
        return companies
    
    
    # Step 1: Login and get cookies with undetected-chromedriver
    print("🌐 Logging into Glassdoor with undetected-chromedriver...")
    
    driver = uc.Chrome(
        headless=False,  # Run in visible mode for login
        version_main=None,  # Auto-detect Chrome version
        use_subprocess=True
    )
    
    try:
        # Go to login page
        driver.get("https://www.glassdoor.com/profile/login_input.htm")
        print("🔍 Browser opened! You have 15 seconds to investigate...")
        time.sleep(15)
        
        # Step 1: Find and fill email
        print("📧 Looking for email field...")
        try:
            email_field = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "inlineUserEmail"))
            )
            print("✅ Found email field!")
            print(f"🔍 Email field attributes: id={email_field.get_attribute('id')}, type={email_field.get_attribute('type')}")
            
            # Try to set the email value using direct JavaScript (like the Java example)
            try:
                # Method 1: Direct JavaScript value assignment with proper events
                driver.execute_script(f"""
                    var emailField = document.getElementById('inlineUserEmail');
                    emailField.value = '{glassdoor_email}';
                    emailField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    emailField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    emailField.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                """)
                print("✅ Email entered with direct JavaScript + events!")
            except Exception as e:
                print(f"❌ Direct JavaScript failed: {e}")
                try:
                    # Method 2: Alternative JavaScript approach
                    driver.execute_script(f"""
                        var emailField = document.querySelector('#inlineUserEmail');
                        emailField.value = '{glassdoor_email}';
                        emailField.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        emailField.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    """)
                    print("✅ Email entered with querySelector + events!")
                except Exception as js_error:
                    print(f"❌ querySelector failed: {js_error}")
                    try:
                        # Method 3: Using the element reference
                        driver.execute_script("""
                            var element = arguments[0];
                            var value = arguments[1];
                            element.value = value;
                            element.dispatchEvent(new Event('input', { bubbles: true }));
                            element.dispatchEvent(new Event('change', { bubbles: true }));
                        """, email_field, glassdoor_email)
                        print("✅ Email entered with element reference + events!")
                    except Exception as ref_error:
                        print(f"❌ Element reference failed: {ref_error}")
                        return companies
            
            # Verify the value was set
            final_value = email_field.get_attribute('value')
            print(f"🔍 Final email field value: {final_value}")
            
            # Wait a moment for the form to recognize the input
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Error finding email field: {e}")
            return companies
        
        # Step 2: Click the "Continue" button after email
        print("➡️ Looking for continue button...")
        try:
            continue_button = driver.find_element(By.CSS_SELECTOR, "button[data-test='continue-with-email-inline']")
            print("✅ Found continue button!")
            continue_button.click()
            print("✅ Continue button clicked!")
        except Exception as e:
            print(f"❌ Error finding continue button: {e}")
            return companies
        
        print("⏳ Waiting for password field to appear...")
        time.sleep(100)  # Give you time to investigate password field
        
        # Step 3: Wait for password field to appear and fill it
        print("🔒 Entering password...")
        password_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "userPassword"))
        )
        password_field.send_keys(glassdoor_password)
        
        # Step 4: Click the final login button
        print("🚀 Clicking login button...")
        login_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit'], button[data-test='password-form-submit']"))
        )
        login_button.click()
        
        # Wait for login to complete
        time.sleep(5)
        
        # Check if login was successful
        if "profile" in driver.current_url or "dashboard" in driver.current_url:
            print("✅ Successfully logged into Glassdoor")
        else:
            print("❌ Login failed - check credentials")
            driver.quit()
            return companies
        
        # Get authenticated cookies
        cookies = driver.get_cookies()
        requests_cookies = {cookie['name']: cookie['value'] for cookie in cookies}
        print(f"✅ Got {len(cookies)} authenticated cookies")
        
    except Exception as e:
        print(f"❌ Error during login: {e}")
        driver.quit()
        return companies
    finally:
        driver.quit()
    
    # Step 2: Use authenticated cookies with requests
    headers = {
        'User-Agent': header,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Referer': 'https://www.glassdoor.com/',
    }
    
    for title in job_titles:
        print(f"\n🔍 Processing job title: {title}")
        title_companies = set()
        
        for page in range(1, 100):
            print(f"   📄 Page {page}...", end=" ")
            
            params = {
                'filterType': 'RATING_CAREER_OPPORTUNITIES', 
                'locId': 1, 
                'locType': 'N', 
                'locName': 'United+States', 
                'sgoc': '1001,1003,1004,1007,1008,1009,1011,1019,1018,1021,1022',
                'occ': title, 
                'page': page, 
                'overall_rating_low': 3.5
            }
            
            try:
                url = f'https://www.glassdoor.com/Reviews/index.htm'
                print(f"Requesting...", end=" ")
                response = requests.get(url, params=params, headers=headers, cookies=requests_cookies)
                print(f"Status: {response.status_code}", end=" ")
                
                if response.status_code != 200:
                    print(f"❌ HTTP Error: {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.text, 'html.parser')
                company_elements = soup.find_all('div', {'data-test': 'employer-short-name'})
                print(f"Found {len(company_elements)} company elements", end=" ")
                
                # Check if page is empty (no more results)
                if len(company_elements) == 0:
                    print("📭 No more companies found - stopping pagination")
                    break
                
                page_companies = 0
                for element in company_elements:
                    company_name = element.text.strip()
                    if company_name:
                        title_companies.add(company_name)
                        page_companies += 1
                        print(f"     + {company_name}")
                
                print(f"Added {page_companies} new companies")
                
                # If we got very few companies, might be at the end
                if page_companies < 5 and page > 1:
                    print("📭 Few companies found - likely end of results")
                    break
                
                time.sleep(2)  # Rate limiting
                
            except Exception as e:
                print(f"❌ Error on page {page} for {title}: {e}")
                print(f"   Response length: {len(response.text) if 'response' in locals() else 'N/A'}")
                break
        
        print(f"   ✅ Total companies for {title}: {len(title_companies)}")
        companies.update(title_companies)
    
    print(f"\n🏆 Total unique Glassdoor companies: {len(companies)}")
    return companies

if __name__ == "__main__":
    forbes = get_forbes_ai50()
    cb = get_cb_insights()
    yc = set(get_yc_companies())
    glassdoor = get_glassdoor_companies()

    print(f"   Found {len(yc)} YC companies")
    print(f"   Found {len(glassdoor)} Glassdoor companies")

    

