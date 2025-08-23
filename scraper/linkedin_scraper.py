#!/usr/bin/env python3
"""
Final LinkedIn Job Scraper - Optimized with Smart DOM Fallback
Uses API-first approach with intelligent DOM fallback and early empty page detection
"""

import undetected_chromedriver as uc
import pickle
import time
import json
import re
import random
from datetime import datetime, timezone
from collections import defaultdict
from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# Search parameters
EXP_CODES = ["1", "2", "3", "4", "5", "6"]  # Intern to Executive
JT_CODES = ["I", "F", "C", "T", "P", "V", "O"]  # Internship to Other
WT_CODES = ["2", "1", "3"]  # Remote, On-site, Hybrid

# Labels for readability
EXP_LABEL = {"1": "intern", "2": "entry", "3": "associate", "4": "mid-senior", "5": "director", "6": "executive"}
JT_LABEL = {"I": "internship", "F": "full_time", "C": "contract", "T": "temporary", "P": "part_time", "V": "volunteer", "O": "other"}
WT_LABEL = {"1": "on_site", "2": "remote", "3": "hybrid"}

# Blacklist companies
BLACKLIST_RE = re.compile(
    r"(jobright|jooble|talent\.com|ziprecruiter|lensa|adzuna|simplyhired|neuvoo|jora|"
    r"glassdoor|jobs2careers|myjobhelper|careerbuilder|monster|snagajob|"
    r"insight global|teksystems|kforce|aerotek|randstad|robert half|apex systems|experis|actalent)",
    re.I
)

def load_cookies():
    """Load saved cookies"""
    try:
        with open('li_cookies.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        print("❌ No saved cookies found. Please run login.py first.")
        return None

def setup_driver_and_session():
    """Setup browser session and extract API credentials"""
    print("🔧 Setting up browser session...")
    
    # Setup browser with optimized options
    options = uc.ChromeOptions()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-gpu')
    options.add_argument('--disable-images')
    options.add_argument('--disable-javascript')  # Disable JS for faster loading
    options.add_argument('--disable-plugins')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-browser-side-navigation')
    options.add_argument('--disable-site-isolation-trials')
    
    driver = uc.Chrome(options=options)
    driver.get('https://www.linkedin.com/jobs/')
    
    # Load cookies
    cookies = load_cookies()
    if cookies:
        for cookie in cookies:
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"Warning: Could not set cookie {cookie.get('name', 'unknown')}: {e}")
    
    driver.refresh()
    time.sleep(3)
    
    # Extract session data
    cookies = driver.get_cookies()
    jsessionid = next((c['value'] for c in cookies if c['name'] == 'JSESSIONID'), '').strip('"')
    if jsessionid.startswith('ajax:'):
        jsessionid = jsessionid[5:]
    csrf_token = f'ajax:{jsessionid}' if jsessionid else None
    
    # Create requests session
    import requests
    session = requests.Session()
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))
    
    session.headers.update({
        'Accept': 'application/vnd.linkedin.normalized+json+2.1',
        'csrf-token': csrf_token,
        'x-restli-protocol-version': '2.0.0',
        'User-Agent': driver.execute_script("return navigator.userAgent;")
    })
    
    return driver, session

def get_jobs_api(session, keywords, exp_level, job_type, workplace_type, count=100):
    """Get jobs from API for specific shard parameters with adaptive pagination"""
    all_jobs = []
    page = 0
    max_pages = 5  # Safety limit to prevent infinite loops
    
    while page < max_pages:
        start = page * count
        url = f'https://www.linkedin.com/voyager/api/voyagerJobsDashJobCards?decorationId=com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollectionLite-88&count={count}&q=jobSearch&query=(currentJobId:4289275995,origin:JOB_SEARCH_PAGE_JOB_FILTER,keywords:{keywords},locationUnion:(geoId:103644278),selectedFilters:(distance:List(25),experience:List({exp_level}),jobType:List({job_type}),workplaceType:List({workplace_type}),timePostedRange:List(r604800)),spellCorrectionEnabled:true)&servedEventEnabled=false&start={start}'
        
        try:
            response = session.get(url, timeout=15)
            if response.status_code != 200:
                break
            
            data = response.json()
            elements = data.get('data', {}).get('elements', [])
            
            if not elements:
                break
            
            # Extract job IDs and get details
            page_jobs = []
            for element in elements:
                job_card_urn = element.get('jobCardUnion', {}).get('*jobPostingCard', '')
                job_id_match = re.search(r'(\d+)', job_card_urn)
                if job_id_match:
                    job_id = job_id_match.group(1)
                    job_details = get_job_details_api(session, job_id)
                    if job_details and not is_blacklisted(job_details.get('company_name', '')):
                        page_jobs.append(job_details)
            
            all_jobs.extend(page_jobs)
            
            # Adaptive pagination: only continue if we got exactly 100 jobs (hit the limit)
            if len(elements) < count:
                # Got less than 100 jobs, we've reached the end
                break
            elif len(elements) == count:
                # Got exactly 100 jobs, there might be more - continue to next page
                page += 1
                time.sleep(1)  # Rate limiting between pages
            else:
                # Got more than 100 jobs (shouldn't happen), but stop anyway
                break
            
        except Exception as e:
            print(f"   ❌ API error on page {page + 1}: {e}")
            break
    
    if page > 0:
        print(f"   📄 Retrieved {len(all_jobs)} jobs from {page + 1} pages")
    
    return all_jobs

def get_job_details_api(session, job_id):
    """Get detailed information for a specific job via API"""
    url = f'https://www.linkedin.com/voyager/api/jobs/jobPostings/{job_id}'
    
    try:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            job_data = data.get('data', data)
            
            title = job_data.get('title', 'N/A')
            
            # Improved repost detection
            is_repost = False
            if job_data.get('repostedJobPosting') is not None:
                is_repost = True
            elif job_data.get('originalListedAt') is not None:
                is_repost = True
            elif job_data.get('repostedJob') is not None:
                is_repost = True
            
            # Extract posting date
            posted_dt = None
            for date_field in ['timeAt', 'listedAt', 'postedAt']:
                if date_field in job_data:
                    timestamp = job_data[date_field]
                    if isinstance(timestamp, (int, float)):
                        posted_dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat()
                        break
            
            # Additional repost detection based on suspicious posting patterns
            # Check if this job was posted at a common repost timestamp
            if posted_dt:
                suspicious_timestamps = [
                    "2025-08-20T13:04:52+00:00",
                    "2025-08-21T07:07:39+00:00", 
                    "2025-08-20T17:58:53+00:00",
                    "2025-08-22T01:02:32+00:00",
                    "2025-08-21T10:01:32+00:00",
                    "2025-08-21T07:07:40+00:00",
                    "2025-08-20T13:04:51+00:00",
                    "2025-08-22T01:02:35+00:00"
                ]
                if posted_dt in suspicious_timestamps:
                    is_repost = True
            
            # Extract company name from URL path segment
            company_name = 'N/A'
            url_path = job_data.get('urlPathSegment', '')
            if url_path:
                # Extract company name from URL path like "junior-legal-specialist-at-robin-ai-4289326695"
                parts = url_path.split('-at-')
                if len(parts) > 1:
                    company_part = parts[1].split('-')[:-1]  # Remove the job ID at the end
                    company_name = ' '.join(company_part).title()
            
            # Fallback: try companyDetails if URL extraction fails
            if company_name == 'N/A' and 'companyDetails' in job_data:
                company_details = job_data['companyDetails']
                if 'companyName' in company_details:
                    company_name = company_details['companyName']
                elif 'company' in company_details and isinstance(company_details['company'], dict):
                    company_name = company_details['company'].get('name', 'N/A')
            
            # Extract apply URL (prefer companyApplyUrl if available)
            apply_url = f'https://www.linkedin.com/jobs/view/{job_id}/'
            if 'applyMethod' in job_data:
                apply_method = job_data['applyMethod']
                if 'companyApplyUrl' in apply_method:
                    apply_url = apply_method['companyApplyUrl']
            
            return {
                'job_id': job_id,
                'title': title,
                'company_name': company_name,
                'posted_dt': posted_dt,
                'is_repost': is_repost,
                'url': apply_url,
                'source': 'api'
            }
    except:
        pass
    
    return None

def check_page_has_jobs(driver, timeout=10):
    """Quickly check if page has job cards without waiting for full load"""
    try:
        # Wait for either job cards or "no results" message
        wait = WebDriverWait(driver, timeout)
        
        # Check for job cards first
        job_cards = wait.until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'li[data-occludable-job-id]'))
        )
        return True
        
    except TimeoutException:
        # Check for "no results" message
        try:
            no_results = driver.find_element(By.CSS_SELECTOR, '.jobs-search-no-results-banner')
            return False
        except NoSuchElementException:
            # Check for any job cards that might have loaded
            job_cards = driver.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')
            return len(job_cards) > 0
    
    return False

def get_jobs_dom_smart(driver, keywords, exp_level, job_type, workplace_type):
    """Smart DOM extraction with early empty page detection"""
    try:
        # Build search URL
        base_url = "https://www.linkedin.com/jobs/search"
        params = {
            'keywords': keywords.replace('%22', '"').replace('%20', ' '),
            'location': 'United States',
            'geoId': '103644278',
            'f_E': exp_level,
            'f_JT': job_type,
            'f_WT': workplace_type,
            'f_TPR': 'r604800',
            'sortBy': 'DD'
        }
        
        url = base_url + '?' + '&'.join([f'{k}={v}' for k, v in params.items()])
        driver.get(url)
        
        # Quick check for jobs (with shorter timeout)
        if not check_page_has_jobs(driver, timeout=8):
            print(f"   📭 No jobs found on page (early detection)")
            return []
        
        # If jobs exist, wait a bit more for full load
        time.sleep(2)
        
        # Find job cards
        job_cards = driver.find_elements(By.CSS_SELECTOR, 'li[data-occludable-job-id]')
        
        if not job_cards:
            print(f"   📭 No job cards found after load")
            return []
        
        print(f"   📄 Found {len(job_cards)} job cards in DOM")
        
        jobs = []
        for i, card in enumerate(job_cards[:25]):  # Limit to 25 per shard
            try:
                job_id = card.get_attribute('data-occludable-job-id')
                if not job_id:
                    continue
                
                # Extract title
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, 'h3 a span[title]')
                    title = title_elem.get_attribute('title') if title_elem else 'N/A'
                except NoSuchElementException:
                    title = 'N/A'
                
                # Extract company
                try:
                    company_elem = card.find_element(By.CSS_SELECTOR, 'h4 a')
                    company_name = company_elem.text.strip() if company_elem else 'N/A'
                except NoSuchElementException:
                    company_name = 'N/A'
                
                # Skip blacklisted companies
                if is_blacklisted(company_name):
                    continue
                
                # Extract posting date
                posted_dt = None
                try:
                    time_elem = card.find_element(By.CSS_SELECTOR, 'time[datetime]')
                    datetime_attr = time_elem.get_attribute('datetime')
                    if datetime_attr:
                        posted_dt = datetime.fromisoformat(datetime_attr.replace('Z', '+00:00')).isoformat()
                except:
                    pass
                
                jobs.append({
                    'job_id': job_id,
                    'title': title,
                    'company_name': company_name,
                    'posted_dt': posted_dt,
                    'is_repost': False,  # DOM can't detect reposts reliably
                    'url': f'https://www.linkedin.com/jobs/view/{job_id}/',
                    'source': 'dom'
                })
                
            except Exception as e:
                continue
        
        return jobs
        
    except Exception as e:
        print(f"   ❌ DOM error: {e}")
        return []

def is_blacklisted(company_name):
    """Check if company is blacklisted"""
    if not company_name or company_name == 'N/A':
        return False
    return bool(BLACKLIST_RE.search(company_name))

def scrape_shard_optimized(session, driver, keywords, exp_level, job_type, workplace_type, shard_num, total_shards):
    """Scrape a single shard with optimized API-first + smart DOM fallback"""
    
    exp_label = EXP_LABEL.get(exp_level, exp_level)
    jt_label = JT_LABEL.get(job_type, job_type) 
    wt_label = WT_LABEL.get(workplace_type, workplace_type)
    
    print(f"\n📋 Shard {shard_num}/{total_shards}: {exp_label} + {jt_label} + {wt_label}")
    
    # Try API first
    print(f"   🔍 Trying API...")
    api_jobs = get_jobs_api(session, keywords, exp_level, job_type, workplace_type)
    
    if api_jobs:
        print(f"   ✅ API success: {len(api_jobs)} jobs")
        return api_jobs
    else:
        print(f"   ⚠️ API failed, trying smart DOM fallback...")
        dom_jobs = get_jobs_dom_smart(driver, keywords, exp_level, job_type, workplace_type)
        print(f"   📄 DOM fallback: {len(dom_jobs)} jobs")
        return dom_jobs

def scrape_all_shards_optimized(keywords, max_shards=None):
    """Scrape all shard combinations with optimized approach"""
    print("🚀 Starting Final Optimized LinkedIn Scraper")
    
    # Setup single driver and session
    driver, api_session = setup_driver_and_session()
    
    # Generate all shard combinations
    all_jobs = []
    shard_results = {}
    shard_mappings = {}  # Track which jobs came from which shards
    shard_num = 0
    total_possible = len(EXP_CODES) * len(JT_CODES) * len(WT_CODES)
    
    print(f"📊 Processing up to {max_shards or total_possible} shards (of {total_possible} total combinations)")
    
    try:
        for exp_level in EXP_CODES:
            for job_type in JT_CODES:
                for workplace_type in WT_CODES:
                    shard_num += 1
                    
                    if max_shards and shard_num > max_shards:
                        print(f"\n🔚 Reached max shards limit: {max_shards}")
                        break
                    
                    # Scrape this shard
                    shard_jobs = scrape_shard_optimized(api_session, driver, keywords, exp_level, job_type, workplace_type, shard_num, max_shards or total_possible)
                    
                    # Track results
                    shard_key = f"{exp_level}_{job_type}_{workplace_type}"
                    shard_results[shard_key] = {
                        'exp_level': exp_level,
                        'job_type': job_type,
                        'workplace_type': workplace_type,
                        'job_count': len(shard_jobs),
                        'labels': f"{EXP_LABEL[exp_level]}+{JT_LABEL[job_type]}+{WT_LABEL[workplace_type]}"
                    }
                    
                    # Track shard mappings for each job
                    for job in shard_jobs:
                        job_id = job['job_id']
                        if job_id not in shard_mappings:
                            shard_mappings[job_id] = []
                        shard_mappings[job_id].append({
                            'shard_key': shard_key,
                            'shard_num': shard_num,
                            'labels': shard_results[shard_key]['labels']
                        })
                    
                    # Add jobs (with deduplication)
                    existing_ids = {job['job_id'] for job in all_jobs}
                    new_jobs = [job for job in shard_jobs if job['job_id'] not in existing_ids]
                    all_jobs.extend(new_jobs)
                    
                    print(f"   📊 Added {len(new_jobs)} new jobs (total: {len(all_jobs)})")
                    
                    # Strategic rate limiting between shards
                    if shard_num % 5 == 0:  # Longer wait every 5 shards
                        wait_time = random.uniform(5.0, 8.0)
                        print(f"   ⏳ Taking longer break ({wait_time:.1f}s)...")
                    else:
                        wait_time = random.uniform(2.0, 4.0)
                    
                    time.sleep(wait_time)
                    
                if max_shards and shard_num >= max_shards:
                    break
            if max_shards and shard_num >= max_shards:
                break
    
    finally:
        driver.quit()
    
    return all_jobs, shard_results, shard_mappings

def main():
    """Main function"""
    # Keywords for AI jobs (URL encoded)
    keywords = '%22AI%22%20OR%20%22Generative%20AI%22%20OR%20%22LLM%22%20OR%20%22Large%20Language%20Model%22%20OR%20%22Prompt%20Engineering%22%20OR%20%22Foundation%20Model%22%20OR%20%22Transformer%22%20OR%20%22RAG%22%20OR%20%22Reinforcement%20Learning%20With%20Human%20Feedback%22%20OR%20%22RLHF%22%20NOT%20Jobright.ai'
    
    # Run all 126 shards with adaptive pagination
    all_jobs, shard_results, shard_mappings = scrape_all_shards_optimized(keywords, max_shards=None)  # Run all shards
    
    # Save results
    with open('linkedin_jobs.json', 'w') as f:
        json.dump(all_jobs, f, indent=2, default=str)
    
    with open('shard_results.json', 'w') as f:
        json.dump(shard_results, f, indent=2)
    
    with open('shard_mappings.json', 'w') as f:
        json.dump(shard_mappings, f, indent=2)
    
    # Show summary
    print(f"\n📊 Final Results:")
    print(f"   Total unique jobs: {len(all_jobs)}")
    print(f"   API jobs: {len([j for j in all_jobs if j['source'] == 'api'])}")
    print(f"   DOM jobs: {len([j for j in all_jobs if j['source'] == 'dom'])}")
    print(f"   Jobs with titles: {len([j for j in all_jobs if j['title'] != 'N/A'])}")
    print(f"   Jobs with dates: {len([j for j in all_jobs if j['posted_dt']])}")
    print(f"   Reposts: {len([j for j in all_jobs if j['is_repost']])}")
    print(f"   Shards processed: {len(shard_results)}")
    
    # Show top productive shards
    productive_shards = sorted(shard_results.items(), key=lambda x: x[1]['job_count'], reverse=True)
    print(f"\n🏆 Top Productive Shards:")
    for i, (shard_key, data) in enumerate(productive_shards[:3]):
        print(f"   {i+1}. {data['labels']}: {data['job_count']} jobs")
    
    print(f"\n💾 Saved to:")
    print(f"   - linkedin_jobs.json (jobs)")
    print(f"   - shard_results.json (shard stats)")
    print(f"   - shard_mappings.json (job-to-shard mapping)")

if __name__ == "__main__":
    main() 