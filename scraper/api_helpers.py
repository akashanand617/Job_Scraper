#!/usr/bin/env python3
"""
LinkedIn API Helper Functions
Uses direct JavaScript approach for reliable API calls
"""

import time
import random
from datetime import datetime, timezone


def get_job_details_api(job_id, driver):
    """
    Get detailed job information using direct JavaScript API call.
    Returns: dict with timeAt, repostedJob, companyName, salary, etc.
    """
    js_code = f"""
    return new Promise((resolve, reject) => {{
        fetch('https://www.linkedin.com/voyager/api/graphql?includeWebMetadata=true&variables=(cardSectionTypes:List(TOP_CARD,HOW_YOU_FIT_CARD),jobPostingUrn:urn:li:fsd_jobPosting:{job_id},includeSecondaryActionsV2:true,jobDetailsContext:(isJobSearch:true))&queryId=voyagerJobsDashJobPostingDetailSections.5b0469809f45002e8d68c712fd6e6285', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/vnd.linkedin.normalized+json+2.1',
                'x-restli-protocol-version': '2.0.0',
                'x-li-lang': 'en_US'
            }}
        }})
        .then(response => {{
            if (!response.ok) {{
                throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
            }}
            return response.json();
        }})
        .then(data => {{
            if (data && data.data && data.data.included && data.data.included.length > 0) {{
                // Look for job posting data in included array
                for (let item of data.data.included) {{
                    if (item.timeAt || item.repostedJob !== undefined) {{
                        resolve({{
                            timeAt: item.timeAt,
                            repostedJob: item.repostedJob || false,
                            companyName: item.companyName,
                            salary: item.salary,
                            requirements: item.requirements,
                            jobType: item.jobType,
                            location: item.location
                        }});
                        return;
                    }}
                }}
            }}
            resolve(null);
        }})
        .catch(error => {{
            console.error('Job details API call failed:', error);
            resolve(null);
        }});
    }});
    """
    
    try:
        result = driver.execute_async_script(js_code)
        if result and result.get('timeAt'):
            # Convert timestamp to datetime
            timestamp = result['timeAt']
            dt = datetime.fromtimestamp(timestamp / 1000, tz=timezone.utc)
            result['posted_dt'] = dt
            print(f"   📅 Got API data for job {job_id}: {dt}")
        return result
    except Exception as e:
        print(f"   ⚠️ Job details API error for {job_id}: {e}")
        return None


def get_repost_status_batch(job_ids, driver, keywords="AI", location="United States"):
    """
    Get repost status for multiple jobs using batch API call.
    Returns: dict mapping job_id -> is_repost
    """
    if not job_ids:
        return {}
    
    # Use the first job ID as currentJobId for the search query
    current_job_id = job_ids[0]
    
    js_code = f"""
    return new Promise((resolve, reject) => {{
        fetch('https://www.linkedin.com/voyager/api/voyagerJobsDashJobCards?decorationId=com.linkedin.voyager.dash.deco.jobs.search.JobSearchCardsCollectionLite-88&count={len(job_ids)}&q=jobSearch&query=(currentJobId:{current_job_id},origin:JOB_SEARCH_PAGE_JOB_FILTER,keywords:"{keywords}",locationUnion:(geoId:103644278),selectedFilters:(distance:List(25),experience:List(1),timePostedRange:List(r86400)),spellCorrectionEnabled:true)&servedEventEnabled=false&start=0', {{
            method: 'GET',
            headers: {{
                'Accept': 'application/vnd.linkedin.normalized+json+2.1',
                'x-restli-protocol-version': '2.0.0',
                'x-li-lang': 'en_US'
            }}
        }})
        .then(response => {{
            if (!response.ok) {{
                throw new Error(`HTTP ${{response.status}}: ${{response.statusText}}`);
            }}
            return response.json();
        }})
        .then(data => {{
            const repostStatus = {{}};
            if (data && data.data && data.data.included) {{
                for (let item of data.data.included) {{
                    if (item.entityUrn && item.repostedJob !== undefined) {{
                        // Extract job ID from entityUrn
                        const match = item.entityUrn.match(/fsd_jobPosting:(\\d+)/);
                        if (match) {{
                            const jobId = match[1];
                            repostStatus[jobId] = item.repostedJob;
                        }}
                    }}
                }}
            }}
            resolve(repostStatus);
        }})
        .catch(error => {{
            console.error('Batch repost API call failed:', error);
            resolve({{}});
        }});
    }});
    """
    
    try:
        result = driver.execute_async_script(js_code)
        if result:
            print(f"   📊 Got repost status for {len(result)} jobs")
        return result or {}
    except Exception as e:
        print(f"   ⚠️ Batch repost API error: {e}")
        return {}


def get_job_details_with_retry(job_id, driver, max_retries=2):
    """
    Get job details with retry logic for reliability.
    """
    for attempt in range(max_retries):
        try:
            result = get_job_details_api(job_id, driver)
            if result:
                return result
            
            # Add delay between retries
            if attempt < max_retries - 1:
                delay = random.uniform(1.0, 3.0)
                time.sleep(delay)
                
        except Exception as e:
            print(f"   ⚠️ Attempt {attempt + 1} failed for job {job_id}: {e}")
            if attempt < max_retries - 1:
                time.sleep(random.uniform(2.0, 5.0))
    
    return None


def batch_get_job_details(job_ids, driver, batch_size=5):
    """
    Get details for multiple jobs in batches to avoid overwhelming the API.
    Returns: dict mapping job_id -> job_details
    """
    results = {}
    
    for i in range(0, len(job_ids), batch_size):
        batch = job_ids[i:i + batch_size]
        print(f"   🔄 Processing batch {i//batch_size + 1} ({len(batch)} jobs)")
        
        for job_id in batch:
            details = get_job_details_with_retry(job_id, driver)
            if details:
                results[job_id] = details
            
            # Small delay between individual jobs
            time.sleep(random.uniform(0.5, 1.5))
        
        # Longer delay between batches
        if i + batch_size < len(job_ids):
            delay = random.uniform(2.0, 4.0)
            print(f"   ⏳ Pausing {delay:.1f}s between batches...")
            time.sleep(delay)
    
    return results


def setup_api_session(driver):
    """
    Setup API session using browser context.
    This is a placeholder for future enhancements.
    """
    print("✅ API session ready (using browser JavaScript)")
    return True 