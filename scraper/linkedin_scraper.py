#!/usr/bin/env python3
"""
LinkedIn Job Scraper - Hybrid API + DOM Approach
Combines left panel parsing with API calls for complete data.
"""

import pickle
import re
import json
import hashlib
import random
import time
import os
import requests
from collections import defaultdict
from fake_useragent import UserAgent
from urllib.parse import quote, urljoin
from datetime import datetime, timezone, timedelta
import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fake_useragent import UserAgent
from dotenv import load_dotenv
import argparse

# Load environment variables
load_dotenv()

# Base search parameters
BASE = {
    "keywords": '"AI" OR "Generative AI" OR "LLM" OR "Large Language Model" OR '
                '"Prompt Engineering" OR "Foundation Model" OR "Transformer" OR '
                '"RAG" OR "Reinforcement Learning With Human Feedback" OR "RLHF"',
    "location": "United States",
    "geoId": "103644278",
    "f_TPR": "r604800",
}

# Facet codes
EXP_CODES = ["1", "2", "3", "4", "5", "6"]
JT_CODES = ["I", "F", "C", "T", "P", "V", "O"]
WT_CODES = ["2", "1", "3"]

# Labels
EXP_LABEL = {"1": "intern", "2": "entry", "3": "associate", "4": "mid-senior", "5": "director", "6": "executive"}
JT_LABEL = {"I": "internship", "F": "full_time", "C": "contract", "T": "temporary", "P": "part_time", "V": "volunteer", "O": "other"}
WT_LABEL = {"1": "on_site", "2": "remote", "3": "hybrid"}

# Blacklist
BLACKLIST_COMPANY_IDS = set()
BLACKLIST_RE = re.compile(
    r"(jobright|jooble|talent\.com|ziprecruiter|lensa|adzuna|simplyhired|neuvoo|jora|"
    r"glassdoor|jobs2careers|myjobhelper|careerbuilder|monster|snagajob|"
    r"insight global|teksystems|kforce|aerotek|randstad|robert half|apex systems|experis|actalent)",
    re.I
)

# Global storage
jobs = {}
shards = {}
jobs_for_shard = defaultdict(list)
shards_for_job = defaultdict(list)

# Session for API calls
api_session = None


def login_and_save_cookies(email, password, user_agent=None, cookie_path="li_cookies.pkl"):
    """
    Launches a Selenium browser, logs into LinkedIn with the provided credentials,
    waits for the landing page to load, then saves cookies to disk.
    """
    opts = uc.ChromeOptions()
    # Don't set custom User-Agent as it causes browser crashes
    # if user_agent:
    #     opts.add_argument(f"--user-agent={user_agent}")
    driver = uc.Chrome(options=opts)
    driver.get("https://www.linkedin.com/login")
    
    # fill in credentials
    driver.find_element(By.ID, "username").send_keys(email)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type=submit]").click()
    
    # wait and enter 2fa if needed
    time.sleep(60)
    driver.get("https://www.linkedin.com")
    # dump cookies
    with open(cookie_path, "wb") as f:
        pickle.dump(driver.get_cookies(), f)
    
    driver.quit()
    print(f"✅ Logged in and saved cookies to {cookie_path}")


def make_driver_with_cookies(cookie_path="li_cookies.pkl", user_agent=None, proxy=None):
    """
    Spins up a ChromeDriver, injects your saved LinkedIn cookies, and returns
    a logged-in driver.  Optionally overrides UA and/or proxy.
    """
    opts = uc.ChromeOptions()
    # Don't set custom User-Agent as it causes browser crashes
    # if user_agent:
    #     opts.add_argument(f"--user-agent={user_agent}")
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")
    driver = uc.Chrome(options=opts)

    # load cookies
    driver.get("https://www.linkedin.com")
    cookies = pickle.load(open(cookie_path, "rb"))
    for c in cookies:
        driver.add_cookie(c)
    driver.refresh()
    time.sleep(3)
    return driver


# Import API helpers
from api_helpers import (
    get_job_details_api, 
    get_repost_status_batch, 
    get_job_details_with_retry,
    batch_get_job_details,
    setup_api_session
)


def is_blacklisted(company_id, company_name):
    """Check if company should be blacklisted."""
    if company_id and company_id in BLACKLIST_COMPANY_IDS: 
        return True
    if company_name and BLACKLIST_RE.search(company_name): 
        return True
    return False


def parse_date(iso: str):
    """Parse date string to datetime."""
    if not iso: 
        return None
    iso = iso.strip()
    if iso.endswith('Z'):
        iso = iso[:-1] + '+00:00'
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
            return datetime.strptime(iso, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return None


def parse_relative_date(relative_str: str):
    """Parse relative date strings like '2 days ago' to datetime."""
    if not relative_str:
        return None
    
    relative_str = relative_str.lower().strip()
    now = datetime.now(timezone.utc)
    
    try:
        # Patterns like "2 days ago", "1 week ago", etc.
        import re
        patterns = [
            (r'(\d+)\s+(day)s?\s+ago', lambda x: now - timedelta(days=int(x))),
            (r'(\d+)\s+(week)s?\s+ago', lambda x: now - timedelta(weeks=int(x))),
            (r'(\d+)\s+(month)s?\s+ago', lambda x: now - timedelta(days=int(x)*30)),
            (r'(\d+)\s+(hour)s?\s+ago', lambda x: now - timedelta(hours=int(x))),
            (r'(\d+)\s+(minute)s?\s+ago', lambda x: now - timedelta(minutes=int(x))),
        ]
        
        for pattern, converter in patterns:
            match = re.search(pattern, relative_str)
            if match:
                number = match.group(1)
                return converter(number)
        
        # Handle "just now", "today", etc.
        if 'just now' in relative_str or 'today' in relative_str:
            return now
        if 'yesterday' in relative_str:
            return now - timedelta(days=1)
            
    except Exception:
        pass
    
    return None


# Old API functions removed - now using api_helpers.py


def parse_date_from_card(card):
    """
    Parse date from left panel job card.
    Returns posted_dt or None.
    """
    posted_dt = None
    
    # Strategy 1: Standard date parsing with multiple selectors
    date_selectors = [
        'time[datetime]',
        '.job-card-container__footer-item time[datetime]',
        '.job-card-list__footer-wrapper time[datetime]',
        '.job-card-container__metadata-wrapper time[datetime]',
        '.artdeco-entity-lockup__metadata time[datetime]',
        'li:not(.job-card-container__footer-item) time[datetime]'
    ]
    
    for selector in date_selectors:
        try:
            date_elem = card.select_one(selector)
            if date_elem:
                datetime_attr = date_elem.get('datetime')
                posted_dt = parse_date(datetime_attr)
                if posted_dt:
                    break
        except:
            continue
    
    # Strategy 2: Text-based extraction (fallback)
    if not posted_dt:
        card_text = card.get_text().lower()
        import re
        date_patterns = [
            r'(\d+)\s+(day|week|month|hour)s?\s+ago',
            r'(\d+)\s+(day|week|month|hour)\s+ago',
            r'(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
            r'(\d{4}-\d{2}-\d{2})'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, card_text, re.IGNORECASE)
            if match:
                posted_dt = parse_relative_date(match.group(0))
                break
    
    return posted_dt


def build_url(p, start):
    """Build LinkedIn job search URL."""
    return (
        "https://www.linkedin.com/jobs/search"
        f"?keywords={quote(p['keywords'])}"
        f"&location={quote(BASE['location'])}"
        f"&geoId={p['geoId']}"
        f"&f_TPR={p['f_TPR']}"
        f"&f_E={p['f_E']}"
        f"&f_JT={p['f_JT']}"
        f"&f_WT={p['f_WT']}"
        f"&start={start}"
        f"&f_VJ=true"
        f"&sortBy=DD"  # Date Descending - most recent first
    )


def shard_key(params: dict) -> str:
    """Generate stable hash for shard."""
    packed = json.dumps(params, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha1(packed).hexdigest()


def register_shard(shards: dict, params: dict, sig: tuple, rank: int):
    """Register a new shard."""
    sid = shard_key(params)
    if sid not in shards:
        fE, fJT, fWT = sig
        shards[sid] = {
            "rank": rank,
            "params": params,
            "sig": sig,
            "meta": {
                "kw_lbl": "catch_all",
                "geo_lbl": "US",
                "experience_lbl": EXP_LABEL.get(fE, fE),
                "job_type_lbl": JT_LABEL.get(fJT, fJT),
                "workplace_lbl": WT_LABEL.get(fWT, fWT),
                "date_from": None,
                "date_to": None,
            }
        }
    return sid


def page_has_no_results(driver):
    """Check if page has no search results."""
    no_results_selectors = [
        'div[class*="no-results"]',
        'div[class*="empty"]',
        'div[class*="no-jobs"]',
        '.jobs-search-no-results-banner',
        '.jobs-search-results-list__no-jobs-available-card'
    ]
    
    for selector in no_results_selectors:
        if driver.find_elements(By.CSS_SELECTOR, selector):
            print(f"   🚫 Found no-results selector: {selector}")
            return True
    
    # Check for job cards directly
    job_cards = driver.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')
    print(f"   🔍 Found {len(job_cards)} job cards on page")
    
    if len(job_cards) == 0:
        print(f"   🚫 No job cards found on page")
        return True
    
    # Check for empty state text (simplified approach)
    page_text = driver.page_source.lower()
    empty_indicators = [
        'no matching jobs found',
        'we couldn\'t find any jobs',
        'no results found'
    ]
    
    for indicator in empty_indicators:
        if indicator in page_text:
            print(f"   🚫 Found empty indicator: {indicator}")
            return True
    
    return False


def parse_cards_from_ul_html(ul_outer_html, driver=None, blacklist_companies=None):
    """Parse job cards from HTML with hybrid date extraction and API enhancement."""
    if blacklist_companies is None:
        blacklist_companies = BLACKLIST_COMPANY_IDS

    soup = BeautifulSoup(ul_outer_html, 'html.parser')
    job_cards = soup.select('li[data-occludable-job-id]')
    
    print(f"   🔍 Found {len(job_cards)} job cards in HTML")
    
    # Collect job IDs for batch repost status lookup
    job_ids = []
    job_data = []
    processed_count = 0
    blacklisted_count = 0
    
    for card in job_cards:
        job_id = card.get('data-occludable-job-id')
        if not job_id:
            continue
        
        job_link = card.select_one('a.job-card-container__link')
        if not job_link:
            continue
        
        href = job_link.get('href', '')
        url = urljoin('https://www.linkedin.com', href)
        
        title = job_link.get('aria-label', '').strip()
        if not title:
            title_elem = job_link.select_one('strong')
            title = title_elem.get_text(strip=True) if title_elem else "N/A"
        
        # Remove "with verification" suffix from titles
        if title.endswith(' with verification'):
            title = title[:-17].strip()
        
        company_elem = card.select_one('.artdeco-entity-lockup__subtitle span')
        company_name = company_elem.get_text(strip=True) if company_elem else "N/A"
        
        company_id = None
        company_link = card.select_one('.artdeco-entity-lockup__subtitle a')
        if company_link:
            company_href = company_link.get('href', '')
            company_id_match = re.search(r'/company/(\d+)', company_href)
            if company_id_match:
                company_id = company_id_match.group(1)
        
        if is_blacklisted(company_id, company_name):
            if company_id:
                blacklist_companies.add(company_id)
            print(f"   🚫 Blacklisted: {company_name} (ID: {company_id})")
            blacklisted_count += 1
            continue
        
        processed_count += 1
        
        # Strategy 1: Parse date from left panel
        posted_dt = parse_date_from_card(card)
        
        # Strategy 2: Use API if left panel failed
        if not posted_dt and driver:
            print(f"   🔍 Trying API for job {job_id} (no date found in left panel)")
            api_details = get_job_details_with_retry(job_id, driver)
            if api_details and api_details.get('posted_dt'):
                posted_dt = api_details['posted_dt']
        
        job_ids.append(job_id)
        job_data.append({
            "job_id": job_id,
            "title": title,
            "posted_dt": posted_dt,
            "company_name": company_name,
            "url": url,
        })
    
    # Get repost status for all jobs in batch
    repost_status = {}
    if job_ids and driver:
        repost_status = get_repost_status_batch(job_ids, driver)
    
    # Combine data with repost status
    for job in job_data:
        job_id = job["job_id"]
        job["is_repost"] = repost_status.get(job_id, False)
        yield job
    
    print(f"   📊 Processing summary: {processed_count} processed, {blacklisted_count} blacklisted, {len(job_data)} yielded")


def add_job_links(jid: str, sid: str, jobs_for_shard: dict, shards_for_job: dict):
    """Link jobs to shards."""
    if not jobs_for_shard[sid] or jobs_for_shard[sid][-1] != jid:
        jobs_for_shard[sid].append(jid)
    if sid not in shards_for_job[jid]:
        shards_for_job[jid].append(sid)


def human_scroll(driver, pane, steps=5):
    """Human-like scrolling."""
    height = driver.execute_script("return arguments[0].scrollHeight", pane)
    for i in range(steps):
        y = height * (i + 1) / steps
        driver.execute_script("arguments[0].scrollTo(0, arguments[1]);", pane, y)
        time.sleep(random.uniform(0.2, 0.6))


def hover_on_job(driver):
    """Hover over random job card."""
    actions = ActionChains(driver)
    card = random.choice(driver.find_elements(By.CSS_SELECTOR, "li.scaffold-layout__list-item"))
    actions.move_to_element(card).pause(random.uniform(0.5, 1.2)).perform()


def back_and_forth(driver, pane):
    """Back and forth scrolling."""
    driver.execute_script("arguments[0].scrollBy(0, -100);", pane)
    time.sleep(random.uniform(0.3, 0.8))
    driver.execute_script("arguments[0].scrollBy(0, 100);", pane)
    time.sleep(random.uniform(0.3, 0.8))


def progressive_scroll_and_load(driver, pane, max_attempts=20):
    """
    Progressive scrolling to load all lazy-loaded jobs with anti-bot measures.
    Returns True if new content was loaded, False if no more content.
    """
    previous_job_count = 0
    stable_count = 0
    scroll_position = 0
    
    for attempt in range(max_attempts):
        # Get current job count
        current_jobs = pane.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')
        current_count = len(current_jobs)
        
        if current_count > previous_job_count:
            print(f"   📊 Loaded {current_count} jobs (+{current_count - previous_job_count})")
            previous_job_count = current_count
            stable_count = 0
        else:
            stable_count += 1
            
        # If no new jobs loaded for 3 consecutive attempts, we're done
        if stable_count >= 3:
            print(f"   ✅ Finished loading - total jobs: {current_count}")
            break
            
        # Progressive scroll down with anti-bot measures
        scroll_increment = random.randint(600, 1000)  # Random scroll distance
        scroll_position += scroll_increment
        
        driver.execute_script(f"arguments[0].scrollTo(0, {scroll_position});", pane)
        
        # Anti-bot: Variable wait times with human-like patterns
        base_wait = random.uniform(2.0, 4.0)  # Longer base wait
        if attempt % 3 == 0:  # Every 3rd attempt, longer pause
            base_wait += random.uniform(1.0, 2.0)
        time.sleep(base_wait)
        
        # Occasional back-and-forth for human-like behavior
        if attempt % 4 == 0:
            back_and_forth(driver, pane)
            time.sleep(random.uniform(0.5, 1.5))  # Extra pause after back-and-forth
            
        # Hover occasionally with longer pauses
        if attempt % 6 == 0:
            try:
                hover_on_job(driver)
                time.sleep(random.uniform(1.0, 2.0))  # Pause after hover
            except:
                pass  # Ignore hover errors
        
        # Anti-bot: Random micro-pauses
        if random.random() < 0.3:  # 30% chance
            time.sleep(random.uniform(0.5, 1.0))
    
    # Final scroll to very bottom to ensure we got everything
    driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", pane)
    time.sleep(random.uniform(2.0, 3.0))  # Longer final wait
    
    final_jobs = pane.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')
    final_count = len(final_jobs)
    
    if final_count > previous_job_count:
        print(f"   📊 Final scroll loaded {final_count} jobs (+{final_count - previous_job_count})")
    
    return final_count


def scrape_jobs(driver, max_pages=5, max_shards=10):  # Testing with 5 pages and 10 shards
    """Main scraping function - hybrid approach."""
    
    EW = len(WT_CODES)
    EJW = len(JT_CODES) * EW
    total_shards = min(max_shards, len(EXP_CODES) * len(JT_CODES) * len(WT_CODES))
    processed_shards = 0
    
    for e_idx, fE in enumerate(EXP_CODES):
        for j_idx, fJT in enumerate(JT_CODES):
            for w_idx, fWT in enumerate(WT_CODES):
                
                params = dict(BASE, **{"f_E": fE, "f_JT": fJT, "f_WT": fWT})
                rank = e_idx * EJW + j_idx * EW + w_idx
                sid = register_shard(shards, params, (fE, fJT, fWT), rank)

                processed_shards += 1
                print(f"🔍 Processing shard {sid[:6]} rank={rank} ({processed_shards}/{total_shards})")
                
                # Stop after max_shards for testing
                if processed_shards >= max_shards:
                    print(f"🛑 Stopping after {max_shards} shards for testing")
                    return
                
                try:
                    driver.get(build_url(params, start=0))
                    print(f"   🌐 Loaded URL: {driver.current_url}")
                    if page_has_no_results(driver):
                        print(f"❌ No results for shard {sid[:6]} rank={rank} | {params}")
                        continue
                    
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "li[data-occludable-job-id]"))
                    )
                    pane = driver.find_element(By.XPATH, "//ul[li[@data-occludable-job-id]]")

                    for start in range(0, max_pages * 25, 25):
                        try:
                            if start > 0:
                                driver.get(build_url(params, start))
                                time.sleep(2)  # Reduced wait time
                                
                                WebDriverWait(driver, 15).until(
                                    EC.presence_of_element_located((By.CSS_SELECTOR, "li[data-occludable-job-id]"))
                                )
                                pane = driver.find_element(By.XPATH, "//ul[li[@data-occludable-job-id]]")

                            # Progressive scroll to load ALL jobs with lazy loading
                            jobs_loaded = progressive_scroll_and_load(driver, pane)
                            
                            # Extract all loaded jobs
                            html = pane.get_attribute("outerHTML")
                            page_jobs_before = len(jobs)

                            for rec in parse_cards_from_ul_html(html, driver):
                                jid = rec["job_id"]
                                if jid not in jobs:
                                    jobs[jid] = rec
                                add_job_links(jid, sid, jobs_for_shard, shards_for_job)

                            new_jobs_added = len(jobs) - page_jobs_before
                            print(f' ✅ shard {sid[:6]} rank={rank} page {start//25 + 1} | Found {jobs_loaded} jobs on page, added {new_jobs_added} new jobs | Total: {len(jobs)}')
                            
                            # If we didn't get many jobs, this might be the last page
                            if jobs_loaded < 10:
                                print(f"   🔚 Few jobs found ({jobs_loaded}), likely last page for this shard")
                                break
                            
                            # Anti-bot: Random pause between pages
                            page_pause = random.uniform(3.0, 6.0)
                            print(f"   ⏳ Pausing {page_pause:.1f}s before next page...")
                            time.sleep(page_pause)
                            
                        except Exception as page_error:
                            print(f"❌ Error on shard {sid[:6]} page {start//25 + 1}: {page_error}")
                            break  # Move to next shard
                            
                except Exception as shard_error:
                    print(f"❌ Error on shard {sid[:6]} rank={rank}: {shard_error}")
                    continue  # Move to next shard
                
                # Anti-bot: Longer pause between shards
                shard_pause = random.uniform(5.0, 10.0)
                print(f"   ⏳ Pausing {shard_pause:.1f}s before next shard...")
                time.sleep(shard_pause)


def save_results():
    """Save results to files."""
    with open('scraped_jobs.json', 'w') as f:
        json.dump(jobs, f, indent=2, default=str)
    with open('scraped_shards.json', 'w') as f:
        json.dump(shards, f, indent=2, default=str)
    with open('job_shard_mappings.json', 'w') as f:
        mappings = {
            'jobs_for_shard': dict(jobs_for_shard),
            'shards_for_job': dict(shards_for_job)
        }
        json.dump(mappings, f, indent=2)
    print(f"💾 Saved {len(jobs)} jobs and {len(shards)} shards")


def main():
    """Main function - hybrid approach."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='LinkedIn Job Scraper - Hybrid API + DOM Approach',
        epilog='''
Examples:
  python linkedin_scraper.py                    # Default: 5 pages, 10 shards
  python linkedin_scraper.py --max_pages 3      # 3 pages per shard
  python linkedin_scraper.py --max_shards 5     # Process only 5 shards
  python linkedin_scraper.py --max_pages 2 --max_shards 3  # Quick test
        '''
    )
    parser.add_argument('--max_pages', type=int, default=5, 
                       help='Maximum number of pages to scrape per shard (default: 5)')
    parser.add_argument('--max_shards', type=int, default=10,
                       help='Maximum number of shards to process (default: 10)')
    parser.add_argument('--keywords', type=str, 
                       default='"AI" OR "Generative AI" OR "LLM" OR "Large Language Model" OR "Prompt Engineering" OR "Foundation Model" OR "Transformer" OR "RAG" OR "Reinforcement Learning With Human Feedback" OR "RLHF"',
                       help='Search keywords (default: AI-related terms)')
    parser.add_argument('--location', type=str, default='United States',
                       help='Search location (default: United States)')
    
    args = parser.parse_args()
    
    print("🚀 Starting LinkedIn Job Scraper - Hybrid API + DOM Approach")
    print(f"📋 Settings: max_pages={args.max_pages}, max_shards={args.max_shards}")
    print(f"🔍 Keywords: {args.keywords}")
    print(f"📍 Location: {args.location}")
    
    # Clear old data
    global jobs, shards, jobs_for_shard, shards_for_job
    jobs = {}
    shards = {}
    jobs_for_shard = defaultdict(list)
    shards_for_job = defaultdict(list)
    
    driver = None
    
    # Simple approach: try cookies first, then login if needed  
    try:
        driver = make_driver_with_cookies()  # Use default User Agent
        print("✅ Using existing session")
        
        # Setup API session
        setup_api_session(driver)
        
    except Exception as e:
        print(f"❌ Session error: {e}")
        print("🔄 Logging in...")
        
        # Get credentials from .env or user input
        email = os.getenv('LINKEDIN_EMAIL')
        password = os.getenv('LINKEDIN_PASSWORD')
        
        if not email or not password:
            from getpass import getpass
            email = input("LinkedIn email: ")
            password = getpass("LinkedIn password: ")
        
        # Login and save session
        login_and_save_cookies(email, password)
        
        # Load session
        driver = make_driver_with_cookies()  # Use default User Agent
        print("✅ Login successful")
        
        # Setup API session
        setup_api_session(driver)
    
    # Run the scraper
    try:
        scrape_jobs(driver, max_pages=args.max_pages, max_shards=args.max_shards)
        save_results()
        print(f"🎉 Scraping completed! Found {len(jobs)} unique jobs")
        print(f"📊 Processed {args.max_shards} shards (max {len(EXP_CODES) * len(JT_CODES) * len(WT_CODES)} total available)")
    except KeyboardInterrupt:
        print("\n⏹️ Scraping interrupted")
        save_results()
    except Exception as e:
        print(f"❌ Critical error: {e}")
        save_results()
    finally:
        if driver:
            driver.quit()


if __name__ == "__main__":
    main() 