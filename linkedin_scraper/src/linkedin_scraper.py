#!/usr/bin/env python3
"""
LinkedIn Job Scraper - API-Only Approach
Uses LinkedIn's internal API for fast and reliable job scraping
"""

import undetected_chromedriver as uc
import pickle
import time
import json
import re
import random
import asyncio
import aiohttp
from datetime import datetime, timezone
from collections import defaultdict
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import os

# Search parameters
EXP_CODES = ["1", "2", "3", "4", "5", "6"]  # Intern to Executive
JT_CODES = ["I", "F", "C", "T", "P", "V", "O"]  # Internship to Other
WT_CODES = ["2", "1", "3"]  # Remote, On-site, Hybrid

# Labels for readability
EXP_LABEL = {"1": "intern", "2": "entry", "3": "associate", "4": "mid-senior", "5": "director", "6": "executive"}
JT_LABEL = {"I": "internship", "F": "full_time", "C": "contract", "T": "temporary", "P": "part_time", "V": "volunteer", "O": "other"}
WT_LABEL = {"1": "on_site", "2": "remote", "3": "hybrid"}

# Performance configuration
CONCURRENT_WORKERS = 10  # Number of concurrent job detail requests
MAX_PAGES_PER_SHARD = 5  # Maximum pages to fetch per shard
API_TIMEOUT = 15  # API request timeout in seconds
JOB_DETAIL_TIMEOUT = 10  # Job detail request timeout in seconds

# Rate limiting configuration
BASE_DELAY = 1.0  # Base delay between shards
MIN_DELAY = 0.3   # Minimum delay
MAX_DELAY = 5.0   # Maximum delay
BREAK_INTERVAL = 10  # Take longer break every N shards

# Blacklist companies
BLACKLIST_RE = re.compile(
    r"(jobright|jooble|talent\.com|ziprecruiter|lensa|adzuna|simplyhired|neuvoo|jora|"
    r"glassdoor|jobs2careers|myjobhelper|careerbuilder|monster|snagajob|"
    r"insight global|teksystems|kforce|aerotek|randstad|robert half|apex systems|experis|actalent)",
    re.I
)

class AdaptiveRateLimiter:
    """Adaptive rate limiter that adjusts delays based on response patterns"""
    
    def __init__(self, base_delay=BASE_DELAY, max_delay=MAX_DELAY, min_delay=MIN_DELAY):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.min_delay = min_delay
        self.current_delay = base_delay
        self.error_count = 0
        self.success_count = 0
        self.response_times = []
    
    def record_success(self, response_time=None):
        """Record a successful request"""
        self.success_count += 1
        if response_time:
            self.response_times.append(response_time)
            # Keep only last 10 response times
            if len(self.response_times) > 10:
                self.response_times.pop(0)
        
        # Gradually decrease delay on success
        if self.success_count % 3 == 0:  # Every 3 successes
            self.current_delay = max(self.min_delay, self.current_delay * 0.9)
    
    def record_error(self):
        """Record an error and increase delay"""
        self.error_count += 1
        # Increase delay on error
        self.current_delay = min(self.max_delay, self.current_delay * 1.5)
    
    def get_delay(self):
        """Get current delay with some randomization"""
        return random.uniform(self.current_delay * 0.8, self.current_delay * 1.2)
    
    def get_break_delay(self):
        """Get longer delay for strategic breaks"""
        return random.uniform(self.current_delay * 1.2, self.current_delay * 1.5)

def load_cookies():
    """Load saved cookies"""
    try:
        with open('li_cookies.pkl', 'rb') as f:
            return pickle.load(f)
    except FileNotFoundError:
        print("❌ No saved cookies found. Please run login.py first.")
        return None

def setup_session():
    """Setup API session with cookies"""
    print("🔧 Setting up API session...")
    
    # Try to load existing cookies first
    cookies = load_cookies()
    if not cookies:
        print("❌ No saved cookies found. Attempting to login...")
        # Try to login automatically
        try:
            from login import login_and_save_cookies
            import os
            email = os.getenv('LINKEDIN_EMAIL')
            password = os.getenv('LINKEDIN_PASSWORD')
            if email and password:
                login_and_save_cookies(email, password)
                cookies = load_cookies()
                if cookies:
                    print("✅ Auto-login successful!")
                else:
                    print("❌ Auto-login failed.")
                    return None
            else:
                print("❌ No LinkedIn credentials found in environment variables.")
                return None
        except Exception as e:
            print(f"❌ Auto-login failed: {e}")
            return None
    
    # Create requests session directly with existing cookies
    import requests
    session = requests.Session()
    
    # Set cookies in the session
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie.get('domain'))
    
    # Extract JSESSIONID for CSRF token
    jsessionid = next((c['value'] for c in cookies if c['name'] == 'JSESSIONID'), '').strip('"')
    if jsessionid.startswith('ajax:'):
        jsessionid = jsessionid[5:]
    csrf_token = f'ajax:{jsessionid}' if jsessionid else None
    
    # Set headers
    session.headers.update({
        'Accept': 'application/vnd.linkedin.normalized+json+2.1',
        'csrf-token': csrf_token,
        'x-restli-protocol-version': '2.0.0',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36'
    })
    
    print("✅ Session setup complete using existing cookies")
    return session


def get_job_details_concurrent(session, job_ids, max_workers=CONCURRENT_WORKERS):
    """Get detailed information for multiple jobs concurrently"""
    def fetch_single_job(job_id):
        return get_job_details_api(session, job_id)
    
    jobs = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all jobs
        future_to_job_id = {executor.submit(fetch_single_job, job_id): job_id for job_id in job_ids}
        
        # Collect results as they complete
        for future in as_completed(future_to_job_id):
            job_details = future.result()
            if job_details and not is_blacklisted(job_details.get('company_name', '')):
                jobs.append(job_details)
    
    return jobs

def get_jobs_api(session, keywords, exp_level, job_type, workplace_type, count=100, time_filter='r604800'):
    """Get jobs from API for specific shard parameters with adaptive pagination"""
    all_jobs = []
    page = 0
    max_pages = MAX_PAGES_PER_SHARD  # Safety limit to prevent infinite loops
    
    while page < max_pages:
        start = page * count
        url = f'https://www.linkedin.com/voyager/api/voyagerJobsDashJobCards?decorationId=com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollectionLite-88&count={count}&q=jobSearch&query=(currentJobId:4289275995,origin:JOB_SEARCH_PAGE_JOB_FILTER,keywords:{keywords},locationUnion:(geoId:103644278),selectedFilters:(distance:List(25),experience:List({exp_level}),jobType:List({job_type}),workplaceType:List({workplace_type}),timePostedRange:List({time_filter})),spellCorrectionEnabled:true)&servedEventEnabled=false&start={start}'
        
        try:
            response = session.get(url, timeout=API_TIMEOUT)
            if response.status_code != 200:
                break
            
            data = response.json()
            elements = data.get('data', {}).get('elements', [])
            
            if not elements:
                break
            
            # Extract job IDs
            job_ids = []
            for element in elements:
                job_card_urn = element.get('jobCardUnion', {}).get('*jobPostingCard', '')
                job_id_match = re.search(r'(\d+)', job_card_urn)
                if job_id_match:
                    job_ids.append(job_id_match.group(1))
            
            # Fetch job details concurrently
            if job_ids:
                page_jobs = get_job_details_concurrent(session, job_ids)
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
        response = session.get(url, timeout=JOB_DETAIL_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            job_data = data.get('data', data)
            
            title = job_data.get('title', 'N/A')
            
            # Enhanced repost detection using timestamp comparison
            listed_at = job_data.get('listedAt')
            original_listed_at = job_data.get('originalListedAt')
            
            # Use timestamp comparison for accurate repost detection
            if listed_at and original_listed_at:
                is_repost = (listed_at != original_listed_at)
            else:
                # Fallback to repostedJobPosting field if timestamps unavailable
                is_repost = job_data.get('repostedJobPosting', False)
                if is_repost is None:
                    is_repost = False
            
            # Extract posting date
            posted_dt = None
            for date_field in ['timeAt', 'listedAt', 'postedAt']:
                if date_field in job_data:
                    timestamp = job_data[date_field]
                    if isinstance(timestamp, (int, float)):
                        posted_dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc).isoformat()
                        break
            
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
            
            # ===== ENHANCED FIELD EXTRACTION =====
            
            # EASY FIELDS - Direct Access (21 fields)
            skills_description = job_data.get('skillsDescription')
            education_description = job_data.get('educationDescription')
            formatted_salary_description = job_data.get('formattedSalaryDescription')
            industries = job_data.get('industries', [])
            formatted_industries = job_data.get('formattedIndustries', [])
            source_domain = job_data.get('sourceDomain')
            formatted_location = job_data.get('formattedLocation')
            work_remote_allowed = job_data.get('workRemoteAllowed')
            workplace_types = job_data.get('workplaceTypes', [])
            benefits = job_data.get('benefits', [])
            brief_benefits_description = job_data.get('briefBenefitsDescription')
            inferred_benefits = job_data.get('inferredBenefits', [])
            employment_status = job_data.get('employmentStatus')
            formatted_employment_status = job_data.get('formattedEmploymentStatus')
            job_functions = job_data.get('jobFunctions', [])
            formatted_job_functions = job_data.get('formattedJobFunctions', [])
            applies = job_data.get('applies')
            views = job_data.get('views')
            new = job_data.get('new')
            sponsored = job_data.get('sponsored')
            created_at = job_data.get('createdAt')
            
            # MEDIUM FIELDS - Dict/List Extraction (5 fields)
            # Job description (nested text)
            description = ''
            if 'description' in job_data and isinstance(job_data['description'], dict):
                description = job_data['description'].get('text', '')
            
            # Salary insights (dict)
            salary_insights = job_data.get('salaryInsights', {})
            job_compensation_available = salary_insights.get('jobCompensationAvailable')
            
            # Company description (nested text)
            company_description = ''
            if 'companyDescription' in job_data and isinstance(job_data['companyDescription'], dict):
                company_description = job_data['companyDescription'].get('text', '')
            
            # Formatted creation date
            created_at_formatted = None
            if created_at:
                try:
                    created_at_formatted = datetime.fromtimestamp(created_at / 1000, tz=timezone.utc).isoformat()
                except (ValueError, TypeError):
                    created_at_formatted = None
            
            return {
                # Original fields (7)
                'job_id': job_id,
                'title': title,
                'company_name': company_name,
                'posted_dt': posted_dt,
                'is_repost': is_repost,
                'url': apply_url,
                'source': 'api',
                
                # Enhanced fields (26)
                # Skills & Education
                'skills_description': skills_description,
                'education_description': education_description,
                
                # Salary & Compensation
                'formatted_salary_description': formatted_salary_description,
                'salary_insights': salary_insights,
                'job_compensation_available': job_compensation_available,
                
                # Company Information
                'company_description': company_description,
                'industries': industries,
                'formatted_industries': formatted_industries,
                'source_domain': source_domain,
                
                # Location & Remote Work
                'formatted_location': formatted_location,
                'work_remote_allowed': work_remote_allowed,
                'workplace_types': workplace_types,
                
                # Benefits & Perks
                'benefits': benefits,
                'brief_benefits_description': brief_benefits_description,
                'inferred_benefits': inferred_benefits,
                
                # Job Details & Type
                'employment_status': employment_status,
                'formatted_employment_status': formatted_employment_status,
                'job_functions': job_functions,
                'formatted_job_functions': formatted_job_functions,
                
                # Metrics & Statistics
                'applies': applies,
                'views': views,
                'new': new,
                'sponsored': sponsored,
                
                # Job Content
                'description': description,
                
                # Timing
                'created_at': created_at,
                'created_at_formatted': created_at_formatted
            }
    except:
        pass
    
    return None


def is_blacklisted(company_name):
    """Check if company is blacklisted"""
    if not company_name or company_name == 'N/A':
        return False
    return bool(BLACKLIST_RE.search(company_name))

def scrape_shard_api_only(session, keywords, exp_level, job_type, workplace_type, shard_num, total_shards, time_filter='r604800'):
    """Scrape a single shard using API only"""
    
    exp_label = EXP_LABEL.get(exp_level, exp_level)
    jt_label = JT_LABEL.get(job_type, job_type) 
    wt_label = WT_LABEL.get(workplace_type, workplace_type)
    
    print(f"\n📋 Shard {shard_num}/{total_shards}: {exp_label} + {jt_label} + {wt_label}")
    
    # Use API only
    print(f"   🔍 Fetching jobs via API...")
    api_jobs = get_jobs_api(session, keywords, exp_level, job_type, workplace_type, time_filter=time_filter)
    
    if api_jobs:
        print(f"   ✅ API success: {len(api_jobs)} jobs")
        return api_jobs
    else:
        print(f"   📭 No jobs found for this shard")
        return []

def save_progress(all_jobs, shard_results, shard_mappings, completed_shards):
    """Save progress to allow resuming later"""
    progress_data = {
        'all_jobs': all_jobs,
        'shard_results': shard_results,
        'shard_mappings': shard_mappings,
        'completed_shards': completed_shards,
        'timestamp': datetime.now().isoformat()
    }
    
    with open('data/scraping_progress.json', 'w') as f:
        json.dump(progress_data, f, indent=2, default=str)

def load_progress():
    """Load progress from previous run"""
    try:
        with open('data/scraping_progress.json', 'r') as f:
            progress_data = json.load(f)
        
        # Convert job IDs back to strings if needed
        all_jobs = progress_data['all_jobs']
        shard_results = progress_data['shard_results']
        shard_mappings = progress_data['shard_mappings']
        completed_shards = set(progress_data['completed_shards'])
        
        return all_jobs, shard_results, shard_mappings, completed_shards
    except FileNotFoundError:
        return [], {}, {}, set()

def scrape_all_shards_api_only(keywords, max_shards=None, resume=False, time_filter='r604800'):
    """Scrape all shard combinations using API only"""
    print("🚀 Starting LinkedIn Scraper (API-Only)")
    
    # Load progress if resuming
    if resume:
        all_jobs, shard_results, shard_mappings, completed_shards = load_progress()
        if completed_shards:
            print(f"📊 Resuming from previous run: {len(completed_shards)} shards completed")
        else:
            print(f"📊 No previous progress found, starting fresh")
            all_jobs, shard_results, shard_mappings, completed_shards = [], {}, {}, set()
    else:
        all_jobs, shard_results, shard_mappings, completed_shards = [], {}, {}, set()
    
    # Setup API session only
    api_session = setup_session()
    
    # Initialize adaptive rate limiter
    rate_limiter = AdaptiveRateLimiter()
    
    # Load shard priorities for optimal ordering
    priority_shards = load_shard_priorities()
    if priority_shards:
        print(f"📊 Using historical shard priorities for optimal ordering")
    else:
        print(f"📊 No historical data found, using default shard order")
    
    # Generate prioritized shard combinations
    shard_combinations = generate_prioritized_shards(priority_shards)
    
    # Initialize tracking with efficient data structures
    seen_job_ids = {job['job_id'] for job in all_jobs}  # Efficient deduplication set
    shard_num = 0
    total_possible = len(shard_combinations)
    
    print(f"📊 Processing up to {max_shards or total_possible} shards (of {total_possible} total combinations)")
    
    for exp_level, job_type, workplace_type in shard_combinations:
        shard_num += 1
        
        if max_shards and shard_num > max_shards:
            print(f"\n🔚 Reached max shards limit: {max_shards}")
            break
        
        # Skip if already completed
        shard_key = f"{exp_level}_{job_type}_{workplace_type}"
        if shard_key in completed_shards:
            print(f"   ⏭️ Skipping completed shard {shard_num}: {shard_key}")
            continue
        
        # Scrape this shard
        start_time = time.time()
        shard_jobs = scrape_shard_api_only(api_session, keywords, exp_level, job_type, workplace_type, shard_num, max_shards or total_possible, time_filter)
        response_time = time.time() - start_time
        
        # Record performance for rate limiting
        if shard_jobs:
            rate_limiter.record_success(response_time)
        else:
            rate_limiter.record_error()
        
        # Track results
        shard_results[shard_key] = {
            'exp_level': exp_level,
            'job_type': job_type,
            'workplace_type': workplace_type,
            'job_count': len(shard_jobs),
            'labels': f"{EXP_LABEL[exp_level]}+{JT_LABEL[job_type]}+{WT_LABEL[workplace_type]}"
        }
        
        # Efficient deduplication and tracking
        new_jobs_count = 0
        for job in shard_jobs:
            job_id = job['job_id']
            
            # Add shard info directly to job
            job['shard_key'] = shard_key
            job['exp_level'] = exp_level
            job['job_type'] = job_type
            job['workplace_type'] = workplace_type
            job['filters'] = shard_results[shard_key]['labels']
            
            # Add human-readable filter labels for API filtering
            job['experience_level'] = EXP_LABEL.get(exp_level, 'unknown')
            job['job_type_label'] = JT_LABEL.get(job_type, 'unknown')
            job['workplace_type_label'] = WT_LABEL.get(workplace_type, 'unknown')
            
            # Track shard mappings (for backward compatibility)
            if job_id not in shard_mappings:
                shard_mappings[job_id] = []
            shard_mappings[job_id].append({
                'shard_key': shard_key,
                'shard_num': shard_num,
                'labels': shard_results[shard_key]['labels']
            })
            
            # Efficient deduplication
            if job_id not in seen_job_ids:
                seen_job_ids.add(job_id)
                all_jobs.append(job)
                new_jobs_count += 1
        
        # Mark shard as completed
        completed_shards.add(shard_key)
        
        print(f"   📊 Added {new_jobs_count} new jobs (total: {len(all_jobs)})")
        
        # Save progress periodically
        if shard_num % 10 == 0:
            save_progress(all_jobs, shard_results, shard_mappings, list(completed_shards))
            print(f"   💾 Progress saved at shard {shard_num}")
        
        # Adaptive rate limiting
        if shard_num % BREAK_INTERVAL == 0:  # Longer break every N shards
            wait_time = rate_limiter.get_break_delay()
            print(f"   ⏳ Taking longer break ({wait_time:.1f}s)...")
        else:
            wait_time = rate_limiter.get_delay()
        
        time.sleep(wait_time)
    
    return all_jobs, shard_results, shard_mappings

def load_shard_priorities():
    """Load historical shard performance to prioritize productive shards"""
    # Note: shard_results.json was removed during cleanup
    # Using default shard order for now
    return None

def generate_prioritized_shards(priority_shards=None):
    """Generate shard combinations in priority order"""
    if priority_shards:
        # Use historical priority order
        prioritized = []
        for shard_key in priority_shards:
            exp_level, job_type, workplace_type = shard_key.split('_')
            prioritized.append((exp_level, job_type, workplace_type))
        return prioritized
    else:
        # Default order (current behavior)
        shards = []
        for exp_level in EXP_CODES:
            for job_type in JT_CODES:
                for workplace_type in WT_CODES:
                    shards.append((exp_level, job_type, workplace_type))
        return shards

def main():
    """Main function"""
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='LinkedIn Job Scraper')
    parser.add_argument('--max-shards', type=int, help='Maximum number of shards to process')
    parser.add_argument('--resume', action='store_true', help='Resume from previous run')
    parser.add_argument('--mode', choices=['daily', 'weekly'], default='daily', help='Scraping mode: daily (recent jobs) or weekly (broader time range)')
    parser.add_argument('--keywords', type=str, help='Custom search keywords (URL encoded)')
    
    args = parser.parse_args()
    
    # Keywords for AI jobs (URL encoded) - can be overridden by command line
    if args.keywords:
        keywords = args.keywords
    else:
        # Same keywords, different time focus
        keywords = '%22AI%22%20OR%20%22Generative%20AI%22%20OR%20%22LLM%22%20OR%20%22Large%20Language%20Model%22%20OR%20%22Prompt%20Engineering%22%20OR%20%22Foundation%20Model%22%20OR%20%22Transformer%22%20OR%20%22RAG%22%20OR%20%22Reinforcement%20Learning%20With%20Human%20Feedback%22%20OR%20%22RLHF%22%20NOT%20Jobright.ai'
    
    # Set time filter based on mode
    if args.mode == 'daily':
        print("📊 Daily mode: Recent jobs (last 24 hours)")
        time_filter = 'r86400'  # Last 24 hours
    else:
        print("📊 Weekly mode: Broader time range (last week)")
        time_filter = 'r604800'  # Last week
    
    # Clear previous data files
    import os
    json_file = 'data/linkedin_jobs_simplified.json'
    progress_file = 'data/scraping_progress.json'
    
    print("🗑️ Clearing previous data files...")
    if os.path.exists(json_file):
        os.remove(json_file)
        print(f"   ✅ Removed {json_file}")
    if os.path.exists(progress_file) and not args.resume:
        os.remove(progress_file)
        print(f"   ✅ Removed {progress_file}")
    
    # Run scraper with options
    all_jobs, shard_results, shard_mappings = scrape_all_shards_api_only(
        keywords, 
        max_shards=args.max_shards, 
        resume=args.resume,
        time_filter=time_filter
    )
    
    # Save results
    with open('data/linkedin_jobs_simplified.json', 'w') as f:
        json.dump(all_jobs, f, indent=2, default=str)
    
    # Note: shard_lookup.json was removed during cleanup
    # Shard information is now embedded directly in each job
    
    # Show summary
    print(f"\n📊 Final Results:")
    print(f"   Total unique jobs: {len(all_jobs)}")
    print(f"   API jobs: {len([j for j in all_jobs if j['source'] == 'api'])}")
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
    print(f"   - data/linkedin_jobs_simplified.json (jobs with shard info)")
    if args.resume:
        print(f"   - data/scraping_progress.json (resume data)")

if __name__ == "__main__":
    main() 