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
import linkedin_scraper
from linkedin_scraper import scrape_all_shards_api_only


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

# Simple request models
class ScrapeRequest(BaseModel):
    keywords: Optional[str] = None
    max_shards: Optional[int] = 126  # Maximum: 6 exp × 7 job types × 3 workplace types
    mode: Optional[str] = "daily"  # daily or weekly
    experience_levels: Optional[list] = None  # ["intern", "entry", "associate", "mid-senior", "director", "executive"]
    job_types: Optional[list] = None  # ["internship", "full_time", "contract", "temporary", "part_time", "volunteer", "other"]
    workplace_types: Optional[list] = None  # ["remote", "on_site", "hybrid"]

class FilterRequest(BaseModel):
    experience_level: Optional[str] = None  # intern, entry, associate, mid-senior, director, executive
    job_type: Optional[str] = None  # internship, full_time, contract, temporary, part_time, volunteer, other
    workplace_type: Optional[str] = None  # remote, on_site, hybrid
    limit: Optional[int] = 50


# Store active jobs
active_jobs: Dict[str, Dict] = {}

@app.get("/")
@app.head("/")
async def root():
    """Root endpoint"""
    return {
        "message": "LinkedIn Job Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "scrape": "POST /scrape",
            "status": "GET /scrape/{job_id}",
            "jobs": "GET /jobs",
            "latest": "GET /latest",
            "filter": "POST /filter",
            "filters": "GET /filters",
            "health": "GET /health"
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

@app.get("/scrape-now")
@app.head("/scrape-now")
async def scrape_now(background_tasks: BackgroundTasks):
    """Start scraping immediately with default keywords (no JSON needed)"""
    job_id = str(uuid.uuid4())
    
    # Use default keywords and settings
    keywords = DEFAULT_KEYWORDS
    time_filter = 'r86400'  # daily
    max_shards = 126  # Maximum: 6 exp × 7 job types × 3 workplace types
    
    # Store job info
    active_jobs[job_id] = {
        "status": "starting",
        "mode": "daily",
        "keywords": keywords,
        "max_shards": max_shards,
        "started_at": datetime.now().isoformat()
    }
    
    # Start background task (no filters - use all parameters)
    background_tasks.add_task(run_scraper_task, job_id, keywords, max_shards, time_filter, None, None, None)
    
    return {
        "message": "Scraping started with default keywords",
        "job_id": job_id,
        "keywords": keywords,
        "max_shards": max_shards,
        "status_url": f"/scrape/{job_id}"
    }

@app.post("/scrape")
async def start_scrape(request: ScrapeRequest, background_tasks: BackgroundTasks):
    """Start a scraping job"""
    job_id = str(uuid.uuid4())
    
    # Set time filter based on mode
    time_filter = 'r86400' if request.mode == "daily" else 'r604800'
    
    # Use provided keywords or default keywords
    keywords = request.keywords or DEFAULT_KEYWORDS
    
    # Store job info with filters
    active_jobs[job_id] = {
        "status": "starting",
        "mode": request.mode,
        "keywords": keywords,
        "max_shards": request.max_shards,
        "experience_levels": request.experience_levels,
        "job_types": request.job_types,
        "workplace_types": request.workplace_types,
        "started_at": datetime.now().isoformat(),
        "message": f"Starting {request.mode} scrape with filters..."
    }
    
    # Convert human-readable filters to parameter lists
    exp_codes = None
    if request.experience_levels:
        exp_codes = []
        for level in request.experience_levels:
            code = next((code for code, label in EXP_LABEL.items() if label == level), None)
            if code:
                exp_codes.append(code)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid experience level: {level}")
    
    jt_codes = None
    if request.job_types:
        jt_codes = []
        for job_type in request.job_types:
            code = next((code for code, label in JT_LABEL.items() if label == job_type), None)
            if code:
                jt_codes.append(code)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid job type: {job_type}")
    
    wt_codes = None
    if request.workplace_types:
        wt_codes = []
        for workplace_type in request.workplace_types:
            code = next((code for code, label in WT_LABEL.items() if label == workplace_type), None)
            if code:
                wt_codes.append(code)
            else:
                raise HTTPException(status_code=400, detail=f"Invalid workplace type: {workplace_type}")
    
    # Run scraper in background with filters
    background_tasks.add_task(run_scraper_task, job_id, keywords, request.max_shards, time_filter, 
                             exp_codes, jt_codes, wt_codes)
    
    return {
        "job_id": job_id,
        "status": "starting",
        "message": f"{request.mode.capitalize()} scrape initiated",
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

@app.get("/jobs")
async def list_jobs():
    """List all scraped LinkedIn jobs"""
    try:
        if not os.path.exists('data/linkedin_jobs_simplified.json'):
            return {"total_jobs": 0, "jobs": []}
        
        with open('data/linkedin_jobs_simplified.json', 'r') as f:
            all_jobs = json.load(f)
        
        return {
            "total_jobs": len(all_jobs),
            "jobs": all_jobs
        }
    except Exception as e:
        return {"error": f"Error reading jobs: {str(e)}", "total_jobs": 0, "jobs": []}

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
    """Get the latest scraped jobs"""
    try:
        if os.path.exists('data/linkedin_jobs_simplified.json'):
            with open('data/linkedin_jobs_simplified.json', 'r') as f:
                jobs = json.load(f)
            
            return {
                "total_jobs": len(jobs),
                "latest_jobs": jobs[:10],  # Return first 10 jobs
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {"message": "No jobs found", "total_jobs": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading jobs: {str(e)}")

@app.post("/filter")
async def filter_jobs(request: FilterRequest):
    """Filter jobs by experience level, job type, workplace type"""
    try:
        if not os.path.exists('data/linkedin_jobs_simplified.json'):
            return {"message": "No jobs found", "total_jobs": 0, "filtered_jobs": []}
        
        with open('data/linkedin_jobs_simplified.json', 'r') as f:
            all_jobs = json.load(f)
        
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
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error filtering jobs: {str(e)}")

@app.get("/filters")
async def get_available_filters():
    """Get available filter options and current job distribution"""
    try:
        if not os.path.exists('data/linkedin_jobs_simplified.json'):
            return {"message": "No jobs found", "filters": {}}
        
        with open('data/linkedin_jobs_simplified.json', 'r') as f:
            jobs = json.load(f)
        
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

async def run_scraper_task(job_id: str, keywords: str, max_shards: int, time_filter: str, 
                          exp_codes: list = None, jt_codes: list = None, wt_codes: list = None):
    """Background task to run the scraper"""
    try:
        active_jobs[job_id]["status"] = "running"
        active_jobs[job_id]["message"] = "Scraping jobs..."
        print(f"🚀 Starting scraping task {job_id}")
        print(f"📊 Keywords: {keywords}")
        print(f"📊 Max shards: {max_shards}")
        print(f"📊 Time filter: {time_filter}")
        print(f"📊 Experience codes: {exp_codes}")
        print(f"📊 Job type codes: {jt_codes}")
        print(f"📊 Workplace type codes: {wt_codes}")
        
        # Test import first
        try:
            from src.linkedin_scraper import scrape_all_shards_api_only
            print("✅ Scraper import successful")
        except Exception as import_error:
            print(f"❌ Import failed: {import_error}")
            raise
        
        # Run the scraper with filters
        print("🔄 Starting scraper...")
        all_jobs, shard_results, shard_mappings = scrape_all_shards_api_only(
            keywords=keywords,
            max_shards=max_shards,
            resume=False,
            time_filter=time_filter,
            exp_codes=exp_codes,
            jt_codes=jt_codes,
            wt_codes=wt_codes
        )
        
        print(f"✅ Scraping completed: {len(all_jobs)} jobs found")
        
        # Save results
        with open('data/linkedin_jobs_simplified.json', 'w') as f:
            json.dump(all_jobs, f, indent=2, default=str)
        
        # Update job status
        active_jobs[job_id]["status"] = "completed"
        active_jobs[job_id]["message"] = f"Scraping completed: {len(all_jobs)} jobs found"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()
        active_jobs[job_id]["results"] = {
            "total_jobs": len(all_jobs),
            "shards_processed": len(shard_results),
            "file_saved": "data/linkedin_jobs_simplified.json"
        }
        
    except Exception as e:
        print(f"❌ Scraping failed: {str(e)}")
        import traceback
        print(f"❌ Full error: {traceback.format_exc()}")
        active_jobs[job_id]["status"] = "failed"
        active_jobs[job_id]["message"] = f"Scraping failed: {str(e)}"
        active_jobs[job_id]["completed_at"] = datetime.now().isoformat()


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