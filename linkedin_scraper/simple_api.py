#!/usr/bin/env python3
"""
Lightweight FastAPI for LinkedIn Job Scraper
Single file implementation - no auth, no complex routing
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
import os
import subprocess
import uuid
from datetime import datetime
from typing import Dict, Optional
from pydantic import BaseModel

# Import your existing scraper
import sys
sys.path.append('src')


# Create FastAPI app
app = FastAPI(
    title="LinkedIn Job Scraper API",
    description="Simple API for LinkedIn job scraping",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Default keywords for your resume automation
DEFAULT_KEYWORDS = "AI OR Machine Learning OR Data Science OR Generative AI OR LLM OR Large Language Model OR Prompt Engineering OR Foundation Model OR Transformer OR RAG OR Reinforcement Learning With Human Feedback OR RLHF"

# Label mappings (same as in linkedin_scraper.py)
EXP_LABEL = {"1": "intern", "2": "entry", "3": "associate", "4": "mid-senior", "5": "director", "6": "executive"}
JT_LABEL = {"I": "internship", "F": "full_time", "C": "contract", "T": "temporary", "P": "part_time", "V": "volunteer", "O": "other"}
WT_LABEL = {"1": "on_site", "2": "remote", "3": "hybrid"}

# Request models
class ScrapeRequest(BaseModel):
    keywords: Optional[str] = None
    max_shards: Optional[int] = 126  # Maximum: 6 exp × 7 job types × 3 workplace types
    mode: Optional[str] = "daily"  # daily or weekly
    experience_level: Optional[str] = None  # intern, entry, associate, mid-senior, director, executive
    job_type: Optional[str] = None  # internship, full_time, contract, temporary, part_time, volunteer, other
    workplace_type: Optional[str] = None  # remote, on_site, hybrid
    batch_size: Optional[int] = 18  # For Lambda compatibility (7 batches of 18 shards each)
    batch_number: Optional[int] = 1  # Which batch to process (1-7)

class FilterRequest(BaseModel):
    experience_level: Optional[str] = None  # intern, entry, associate, mid-senior, director, executive
    job_type: Optional[str] = None  # internship, full_time, contract, temporary, part_time, volunteer, other
    workplace_type: Optional[str] = None  # remote, on_site, hybrid
    limit: Optional[int] = 50


# Store active jobs
active_jobs: Dict[str, Dict] = {}

# ----------------------------------------------------------------------------
# S3-backed aggregation helpers
# ----------------------------------------------------------------------------
def read_s3_hourly_batches_or_local_analytics() -> list:
    """Read today's hourly batch files from S3; fall back to local analytics file.

    Returns a list of job dicts with duplicates removed by job_id.
    """
    all_jobs = []
    try:
        import boto3
        from datetime import datetime, timezone

        s3_client = boto3.client('s3')
        bucket_name = os.getenv('JOBS_BUCKET', 'linkedin-job-scraper-dev-jobs')
        today = datetime.now(timezone.utc).date()
        prefix = f"jobs/hourly/{today}/"

        response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'].endswith('.json'):
                    file_obj = s3_client.get_object(Bucket=bucket_name, Key=obj['Key'])
                    batch_jobs = json.loads(file_obj['Body'].read().decode('utf-8'))
                    if isinstance(batch_jobs, list):
                        all_jobs.extend(batch_jobs)
                    else:
                        all_jobs.append(batch_jobs)
    except Exception as s3_error:
        print(f"⚠️ S3 read failed: {s3_error}")
        # Fallback to local analytics file
        analytics_file = '/tmp/analytics_historical_jobs.json'
        if os.path.exists(analytics_file):
            try:
                with open(analytics_file, 'r') as f:
                    all_jobs = json.load(f)
            except Exception as local_err:
                print(f"⚠️ Local analytics read failed: {local_err}")

    # Dedupe by job_id
    if all_jobs:
        seen_ids = set()
        unique_jobs = []
        for job in all_jobs:
            job_id = job.get('job_id') or job.get('id')
            if job_id and job_id not in seen_ids:
                seen_ids.add(job_id)
                unique_jobs.append(job)
        all_jobs = unique_jobs

    return all_jobs

@app.get("/")
@app.head("/")
async def root():
    """Root endpoint"""
    return {
        "message": "LinkedIn Job Scraper API - Simplified",
        "version": "2.0.0",
        "endpoints": {
            "scrape": "GET /scrape (manual trigger) or POST /scrape (programmatic)",
            "status": "GET /scrape/{job_id}",
            "analytics_jobs": "GET /analytics-jobs (all accumulated data)",
            "latest": "GET /latest (all jobs from last 24 hours, sorted by date)",
            "filter": "POST /filter (filter analytics data)",
            "filters": "GET /filters (available filter options)",
            "batch_info": "GET /batch-info",
            "health": "GET /health",
            "test": "GET /test-scraper"
        },
        "data_source": {
            "analytics": "analytics_historical_jobs.json (accumulating hourly)"
        },
        "features": {
            "hourly_scraping": "Automatically runs analytics every hour",
            "data_accumulation": "Builds historical dataset over time",
            "batch_processing": "Supports Lambda-compatible batch processing",
            "filtering": "Filter by experience, job type, workplace type"
        }
    }

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/test-scraper")
async def test_scraper():
    """Test if scraper can be imported and basic functions work"""
    try:
        # Test import
        from src.linkedin_scraper import scrape_all_shards_api_only
        print("✅ Scraper import successful")
        
        # Test environment variables
        import os
        email = os.getenv('LINKEDIN_EMAIL')
        password = os.getenv('LINKEDIN_PASSWORD')
        
        return {
            "status": "success",
            "scraper_import": "✅ Working",
            "linkedin_email": "✅ Set" if email else "❌ Missing",
            "linkedin_password": "✅ Set" if password else "❌ Missing",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"❌ Scraper test failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/scrape")
async def start_scrape_manual(
    keywords: Optional[str] = None,
    max_shards: Optional[int] = 126,
    mode: Optional[str] = "daily",
    experience_level: Optional[str] = None,
    job_type: Optional[str] = None,
    workplace_type: Optional[str] = None,
    batch_size: Optional[int] = 18,
    batch_number: Optional[int] = 1,
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Manual scraping trigger via GET request"""
    # Create a ScrapeRequest object from query parameters
    request = ScrapeRequest(
        keywords=keywords,
        max_shards=max_shards,
        mode=mode,
        experience_level=experience_level,
        job_type=job_type,
        workplace_type=workplace_type,
        batch_size=batch_size,
        batch_number=batch_number
    )
    
    # Use the existing POST logic
    return await start_scrape(request, background_tasks)

@app.post("/scrape")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Start a scraping job - runs analytics and accumulates data hourly"""
    job_id = str(uuid.uuid4())
    
    # Set time filter based on mode
    time_filter = 'r3600' if request.mode == "daily" else 'r604800'
    
    # Use provided keywords or default keywords
    keywords = request.keywords or DEFAULT_KEYWORDS
    
    # Use analytics data file for accumulating data
    jobs_file = '/tmp/analytics_historical_jobs.json'
    
    # Store job info with filters and batch info
    active_jobs[job_id] = {
        "status": "starting",
        "mode": "analytics",  # Always run as analytics to accumulate data
        "keywords": keywords,
        "max_shards": request.max_shards,
        "experience_level": request.experience_level,
        "job_type": request.job_type,
        "workplace_type": request.workplace_type,
        "batch_size": request.batch_size,
        "batch_number": request.batch_number,
        "data_file": jobs_file,
        "retention": "accumulating",
        "started_at": datetime.now().isoformat(),
        "message": f"Starting analytics scrape (batch {request.batch_number}) - accumulating data..."
    }
    
    # Convert human-readable filters to parameter lists
    exp_codes = None
    if request.experience_level:
        exp_codes = [code for code, label in EXP_LABEL.items() if label == request.experience_level]
        if not exp_codes:
            raise HTTPException(status_code=400, detail=f"Invalid experience level: {request.experience_level}")
    
    jt_codes = None
    if request.job_type:
        jt_codes = [code for code, label in JT_LABEL.items() if label == request.job_type]
        if not jt_codes:
            raise HTTPException(status_code=400, detail=f"Invalid job type: {request.job_type}")
    
    wt_codes = None
    if request.workplace_type:
        wt_codes = [code for code, label in WT_LABEL.items() if label == request.workplace_type]
        if not wt_codes:
            raise HTTPException(status_code=400, detail=f"Invalid workplace type: {request.workplace_type}")
    
    # Run analytics scraper in background with filters and batch info
    background_tasks.add_task(
        run_analytics_task, 
        job_id, 
        keywords,
        request.max_shards, 
        time_filter,
        exp_codes, 
        jt_codes, 
        wt_codes,
        request.batch_size,
        request.batch_number,
        jobs_file
    )
    
    return {
        "job_id": job_id,
        "status": "starting",
        "message": "Analytics scrape initiated (accumulating data hourly)",
        "data_file": jobs_file,
        "retention": "accumulating",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/scrape/{job_id}")
async def get_scrape_status(job_id: str):
    """Get status of a scraping job"""
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = active_jobs[job_id]
    return {
        "job_id": job_id,
        "status": job["status"],
        "message": job["message"],
        "started_at": job["started_at"],
        "completed_at": job.get("completed_at"),
        "results": job.get("results")
    }

async def run_analytics_task(job_id: str, keywords: str, max_shards: int, time_filter: str,
                           exp_codes: list = None, jt_codes: list = None, wt_codes: list = None,
                           batch_size: int = 18, batch_number: int = 1, jobs_file: str = None):
    """Background task for analytics scraping"""
    try:
        # Ensure job entry exists (scheduled invocations may not pre-register)
        if job_id not in active_jobs:
            active_jobs[job_id] = {
                "status": "queued",
                "message": "Scheduled analytics run",
                "started_at": datetime.now().isoformat(),
            }
        active_jobs[job_id]["status"] = "running"
        active_jobs[job_id]["message"] = "Running analytics scrape..."
        print(f"🚀 Starting analytics task {job_id}")
        print(f"📊 Data file: {jobs_file}")
        print(f"📊 Retention: accumulating")
        
        # Test import first
        try:
            from src.linkedin_scraper import scrape_all_shards_api_only
            print("✅ Scraper import successful")
        except Exception as import_error:
            print(f"❌ Import failed: {import_error}")
            raise
        
        # Run the scraper with filters and batch processing
        print("🔄 Starting analytics scraper...")
        all_jobs, shard_results, shard_mappings = scrape_all_shards_api_only(
            keywords=keywords,
            max_shards=max_shards,
            resume=False,
            time_filter=time_filter,
            exp_codes=exp_codes,
            jt_codes=jt_codes,
            wt_codes=wt_codes,
            batch_size=batch_size,
            batch_number=batch_number
        )
        
        print(f"✅ Analytics scraping completed: {len(all_jobs)} jobs found")
        
        # Load existing analytics data
        existing_jobs = []
        if os.path.exists(jobs_file):
            with open(jobs_file, 'r') as f:
                existing_jobs = json.load(f)
        
        # Merge new jobs with existing (avoid duplicates)
        existing_job_ids = {job.get('job_id') for job in existing_jobs}
        new_jobs = [job for job in all_jobs if job.get('job_id') not in existing_job_ids]
        
        # Combine and save
        combined_jobs = existing_jobs + new_jobs
        with open(jobs_file, 'w') as f:
            json.dump(combined_jobs, f, indent=2, default=str)
        
        print(f"📊 Analytics data updated: {len(new_jobs)} new jobs, {len(combined_jobs)} total")
        
        # Update job status
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["message"] = f"Analytics scrape completed: {len(new_jobs)} new jobs added"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        active_jobs[job_id]["results"] = {
            "new_jobs": len(new_jobs),
            "total_jobs": len(combined_jobs),
            "shards_processed": len(shard_results),
            "batch_number": batch_number,
            "batch_size": batch_size,
            "data_file": jobs_file
        }
        
    except Exception as e:
        print(f"❌ Analytics scraping failed: {str(e)}")
        import traceback
        print(f"❌ Full error: {traceback.format_exc()}")
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["message"] = f"Analytics scraping failed: {str(e)}"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()

@app.get("/analytics-jobs")
async def list_analytics_jobs():
    """List all analytics LinkedIn jobs (accumulating)"""
    try:
        all_jobs = read_s3_hourly_batches_or_local_analytics()
        
        return {
            "total_jobs": len(all_jobs),
            "jobs": all_jobs,
            "retention": "accumulating",
            "data_source": "s3_or_local"
        }
    except Exception as e:
        return {"error": f"Error reading analytics jobs: {str(e)}", "total_jobs": 0, "jobs": []}

@app.get("/scrape-jobs")
async def list_scrape_jobs():
    """List all background scraping jobs (for tracking)"""
    return {
        "total_scrape_jobs": len(active_jobs),
        "scrape_jobs": [
            {
                "job_id": job_id,
                "status": job["status"],
                "mode": job["mode"],
                "started_at": job["started_at"],
                "completed_at": job.get("completed_at"),
                "results": job.get("results")
            }
            for job_id, job in active_jobs.items()
        ]
    }

@app.get("/latest")
async def get_latest_jobs():
    """Get all jobs from the last 24 hours from S3 batch files, sorted by date"""
    try:
        # Try to read from S3 batch files first
        all_jobs = []
        try:
            import boto3
            from datetime import datetime, timezone, timedelta
            
            s3_client = boto3.client('s3')
            bucket_name = os.getenv('JOBS_BUCKET', 'linkedin-job-scraper-dev-jobs')
            
            # Get today's date for the S3 path
            today = datetime.now(timezone.utc).date()
            prefix = f"jobs/hourly/{today}/"
            
            # List all batch files for today
            response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.json'):
                        # Download and parse each batch file
                        file_obj = s3_client.get_object(Bucket=bucket_name, Key=obj['Key'])
                        batch_jobs = json.loads(file_obj['Body'].read().decode('utf-8'))
                        if isinstance(batch_jobs, list):
                            all_jobs.extend(batch_jobs)
                        else:
                            all_jobs.append(batch_jobs)
            
            # Remove duplicates based on job_id
            seen_ids = set()
            unique_jobs = []
            for job in all_jobs:
                job_id = job.get('job_id') or job.get('id')
                if job_id and job_id not in seen_ids:
                    seen_ids.add(job_id)
                    unique_jobs.append(job)
            all_jobs = unique_jobs
            
        except Exception as s3_error:
            print(f"⚠️ S3 consolidation failed: {s3_error}")
            # Fallback to local analytics file
            analytics_file = '/tmp/analytics_historical_jobs.json'
            if not os.path.exists(analytics_file):
                return {"message": "No analytics data found", "total_jobs": 0, "last_24h_jobs": 0, "latest_jobs": []}
            
            with open(analytics_file, 'r') as f:
                all_jobs = json.load(f)
        
        # Filter to last 24 hours
        from datetime import timedelta, timezone
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        last_24h_jobs = []
        
        for job in all_jobs:
            # Check if job was posted in the last 24 hours
            job_datetime = None
            if 'posted_dt' in job and job['posted_dt']:
                try:
                    # Parse the ISO format datetime
                    job_datetime = datetime.fromisoformat(job['posted_dt'].replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    # Try alternative date fields if posted_dt fails
                    for date_field in ['listedAt', 'created_at_formatted']:
                        if date_field in job and job[date_field]:
                            try:
                                job_datetime = datetime.fromisoformat(job[date_field].replace('Z', '+00:00'))
                                break
                            except (ValueError, TypeError):
                                continue
            
            if job_datetime and job_datetime >= cutoff_time:
                last_24h_jobs.append(job)
        
        # Sort jobs by posted date (most recent first)
        last_24h_jobs_sorted = sorted(last_24h_jobs, key=lambda x: x.get('posted_dt', ''), reverse=True)
        
        return {
            "total_jobs": len(all_jobs),
            "last_24h_jobs": len(last_24h_jobs_sorted),
            "latest_jobs": last_24h_jobs_sorted,
            "data_source": "s3_batch_files" if 's3_client' in locals() else "analytics_historical_jobs.json",
            "retention": "accumulating",
            "time_filter": "last_24_hours",
            "cutoff_time": cutoff_time.isoformat(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading analytics jobs: {str(e)}")

@app.post("/filter")
async def filter_jobs(request: FilterRequest):
    """Filter jobs by experience level, job type, workplace type from analytics data"""
    try:
        # Read from S3 (hourly batches) or local analytics fallback
        all_jobs = read_s3_hourly_batches_or_local_analytics()
        if not all_jobs:
            return {"message": "No analytics data found", "total_jobs": 0, "filtered_jobs": []}
        
        # Filter jobs based on request parameters
        filtered_jobs = []
        
        for job in all_jobs:
            # Check experience level filter (use human-readable labels directly)
            if request.experience_level:
                if job.get('experience_level') != request.experience_level:
                    continue
            
            # Check job type filter (use human-readable labels directly)
            if request.job_type:
                if job.get('job_type_label') != request.job_type:
                    continue
            
            # Check workplace type filter (use human-readable labels directly)
            if request.workplace_type:
                if job.get('workplace_type_label') != request.workplace_type:
                    continue
            
            filtered_jobs.append(job)
        
        # Apply limit
        limit = request.limit or 50
        filtered_jobs = filtered_jobs[:limit]
        
        return {
            "total_jobs": len(all_jobs),
            "filtered_jobs": len(filtered_jobs),
            "jobs": filtered_jobs,
            "filters_applied": {
                "experience_level": request.experience_level,
                "job_type": request.job_type,
                "workplace_type": request.workplace_type,
                "limit": limit
            },
            "data_source": "s3_or_local",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error filtering jobs: {str(e)}")

@app.get("/batch-info")
async def get_batch_info():
    """Get information about batch processing for Lambda compatibility"""
    return {
        "total_shards": 126,
        "recommended_batch_size": 18,
        "total_batches": 7,
        "batch_info": {
            "batch_1": "Shards 1-18",
            "batch_2": "Shards 19-36", 
            "batch_3": "Shards 37-54",
            "batch_4": "Shards 55-72",
            "batch_5": "Shards 73-90",
            "batch_6": "Shards 91-108",
            "batch_7": "Shards 109-126"
        },
        "lambda_timeout": "15 minutes",
        "estimated_time_per_batch": "3-5 minutes",
        "usage": "Use batch_number (1-7) and batch_size (18) in POST /scrape"
    }

@app.get("/filters")
async def get_available_filters():
    """Get available filter options and current job distribution from analytics data"""
    try:
        # Read from S3 (hourly batches) or local analytics fallback
        jobs = read_s3_hourly_batches_or_local_analytics()
        if not jobs:
            return {"message": "No analytics data found", "filters": {}}
        
        # Count jobs by each filter category
        exp_counts = {}
        job_type_counts = {}
        workplace_counts = {}
        
        for job in jobs:
            # Experience level counts (use human-readable labels directly)
            exp_label = job.get('experience_level', 'unknown')
            exp_counts[exp_label] = exp_counts.get(exp_label, 0) + 1
            
            # Job type counts (use human-readable labels directly)
            jt_label = job.get('job_type_label', 'unknown')
            job_type_counts[jt_label] = job_type_counts.get(jt_label, 0) + 1
            
            # Workplace type counts (use human-readable labels directly)
            wt_label = job.get('workplace_type_label', 'unknown')
            workplace_counts[wt_label] = workplace_counts.get(wt_label, 0) + 1
        
        return {
            "total_jobs": len(jobs),
            "filters": {
                "experience_levels": {
                    "options": ["intern", "entry", "associate", "mid-senior", "director", "executive"],
                    "counts": exp_counts
                },
                "job_types": {
                    "options": ["internship", "full_time", "contract", "temporary", "part_time", "volunteer", "other"],
                    "counts": job_type_counts
                },
                "workplace_types": {
                    "options": ["remote", "on_site", "hybrid"],
                    "counts": workplace_counts
                }
            },
            "data_source": "s3_or_local",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting filters: {str(e)}")

# Helper functions to convert codes to labels
def get_exp_label(code: str) -> str:
    """Convert experience level code to label"""
    exp_labels = {"1": "intern", "2": "entry", "3": "associate", "4": "mid-senior", "5": "director", "6": "executive"}
    return exp_labels.get(code, "unknown")

def get_job_type_label(code: str) -> str:
    """Convert job type code to label"""
    jt_labels = {"I": "internship", "F": "full_time", "C": "contract", "T": "temporary", "P": "part_time", "V": "volunteer", "O": "other"}
    return jt_labels.get(code, "unknown")

def get_workplace_type_label(code: str) -> str:
    """Convert workplace type code to label"""
    wt_labels = {"1": "on_site", "2": "remote", "3": "hybrid"}
    return wt_labels.get(code, "unknown")



if __name__ == "__main__":
    print("🚀 Starting LinkedIn Scraper API")
    print("📖 API docs: http://localhost:8000/docs")
    print("�� Health check: http://localhost:8000/health")
    
    uvicorn.run(
        "simple_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )