"""
FastAPI router for all ATS endpoints.
Mounted on the main app at /ats prefix.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from typing import Optional

from .models import (
    MatchRequest,
    AIAnalysisRequest,
    ResumeUploadResponse,
    BatchMatchResponse,
)
from . import storage
from .resume_parser import parse_resume
from .skill_extractor import extract_skills_from_text
from .match_scorer import batch_score, score_match
from .ai_analyzer import analyze_resume_job_fit, ai_parse_resume

ats_router = APIRouter(prefix="/ats", tags=["ATS Resume Analyzer"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Helper: load jobs from the scraper's data store
# ---------------------------------------------------------------------------

def _load_scraped_jobs():
    """Load jobs using the existing scraper data pipeline."""
    import sys, os
    # Import from sibling module
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from simple_api import read_s3_hourly_batches_or_local_analytics
    return read_s3_hourly_batches_or_local_analytics()


def _find_job_by_id(jobs, job_id: str) -> Optional[dict]:
    """Find a specific job by ID from the jobs list."""
    for job in jobs:
        if str(job.get("job_id")) == str(job_id):
            return job
    return None


# ---------------------------------------------------------------------------
# Resume Upload & Management
# ---------------------------------------------------------------------------

@ats_router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    ai_parse: bool = Query(False, description="Use AI-enhanced parsing for better accuracy"),
):
    """Upload a PDF or DOCX resume. Returns parsed resume data with extracted skills."""
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "docx", "doc"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{ext}. Please upload a PDF or DOCX file.",
        )

    # Read file content
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(file_bytes) / 1024 / 1024:.1f} MB). Maximum size is 5 MB.",
        )

    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Parse resume
    try:
        parsed = await parse_resume(file.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    # Optionally enhance with AI parsing
    if ai_parse:
        try:
            ai_data = await ai_parse_resume(parsed.raw_text)
            # Merge AI results into parsed resume
            if ai_data.get("name") and not parsed.contact_info.name:
                parsed.contact_info.name = ai_data["name"]
            if ai_data.get("email") and not parsed.contact_info.email:
                parsed.contact_info.email = ai_data["email"]
            if ai_data.get("skills"):
                # Merge skills
                existing = {s.lower() for s in parsed.skills}
                for skill in ai_data["skills"]:
                    if skill.lower() not in existing:
                        parsed.skills.append(skill)
                        existing.add(skill.lower())
            if ai_data.get("summary") and not parsed.summary:
                parsed.summary = ai_data["summary"]
            parsed.parse_method = "ai_enhanced"
        except Exception as e:
            print(f"Warning: AI parsing failed, using rule-based results: {e}")

    # Extract skills from full text using taxonomy
    taxonomy_skills = extract_skills_from_text(parsed.raw_text)
    existing = {s.lower() for s in parsed.skills}
    for skill in taxonomy_skills:
        if skill.lower() not in existing:
            parsed.skills.append(skill)
            existing.add(skill.lower())

    # Save resume file and parsed data
    await storage.save_resume_file(parsed.resume_id, file.filename, file_bytes)
    await storage.save_parsed_resume(parsed)

    return ResumeUploadResponse(
        resume_id=parsed.resume_id,
        filename=file.filename,
        status="parsed",
        skills_found=len(parsed.skills),
        experience_count=len(parsed.work_experience),
        education_count=len(parsed.education),
        message=f"Resume parsed successfully ({parsed.parse_method}). "
        f"Found {len(parsed.skills)} skills, "
        f"{len(parsed.work_experience)} work experiences, "
        f"{len(parsed.education)} education entries.",
    )


@ats_router.get("/resumes")
async def list_resumes():
    """List all uploaded resumes."""
    resumes = await storage.list_resumes()
    return {
        "total_resumes": len(resumes),
        "resumes": resumes,
    }


@ats_router.get("/resumes/{resume_id}")
async def get_resume(resume_id: str):
    """Get full parsed resume details."""
    parsed = await storage.load_parsed_resume(resume_id)
    if not parsed:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
    return parsed


@ats_router.delete("/resumes/{resume_id}")
async def delete_resume(resume_id: str):
    """Delete a resume and all associated analyses."""
    deleted = await storage.delete_resume(resume_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")
    return {"message": f"Resume {resume_id} and associated data deleted"}


# ---------------------------------------------------------------------------
# Match Scoring
# ---------------------------------------------------------------------------

@ats_router.post("/match", response_model=BatchMatchResponse)
async def match_resume_to_jobs(request: MatchRequest):
    """Score a resume against scraped jobs.

    Uses deterministic keyword/skill matching for fast batch scoring.
    If job_ids is provided, matches only against those jobs.
    Otherwise matches against all available scraped jobs.
    """
    # Load resume
    parsed = await storage.load_parsed_resume(request.resume_id)
    if not parsed:
        raise HTTPException(
            status_code=404, detail=f"Resume {request.resume_id} not found"
        )

    # Load jobs
    all_jobs = _load_scraped_jobs()
    if not all_jobs:
        raise HTTPException(
            status_code=404,
            detail="No scraped job data available. Run a scrape first.",
        )

    # Filter to specific job IDs if provided
    if request.job_ids:
        target_ids = set(request.job_ids)
        jobs_to_score = [j for j in all_jobs if str(j.get("job_id")) in target_ids]
        if not jobs_to_score:
            raise HTTPException(
                status_code=404,
                detail="None of the specified job_ids were found in scraped data.",
            )
    else:
        jobs_to_score = all_jobs

    # Run batch scoring
    matches = batch_score(
        resume=parsed,
        jobs=jobs_to_score,
        top_n=request.top_n or 10,
        min_score=request.min_score or 0.0,
    )

    result = BatchMatchResponse(
        resume_id=request.resume_id,
        total_jobs_compared=len(jobs_to_score),
        matches=matches,
    )

    # Cache results
    await storage.save_match_results(request.resume_id, result)

    return result


@ats_router.get("/match/{resume_id}")
async def get_cached_matches(resume_id: str):
    """Get cached match results for a resume."""
    results = await storage.load_match_results(resume_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No match results found for resume {resume_id}. Run POST /ats/match first.",
        )
    return results


# ---------------------------------------------------------------------------
# AI Analysis
# ---------------------------------------------------------------------------

@ats_router.post("/analyze")
async def analyze_resume_job(request: AIAnalysisRequest):
    """Deep AI analysis of a specific resume-job pair using Claude.

    Provides detailed strengths, weaknesses, optimization suggestions,
    and a rewritten professional summary tailored to the job.
    """
    # Load resume
    parsed = await storage.load_parsed_resume(request.resume_id)
    if not parsed:
        raise HTTPException(
            status_code=404, detail=f"Resume {request.resume_id} not found"
        )

    # Load job
    all_jobs = _load_scraped_jobs()
    job = _find_job_by_id(all_jobs, request.job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail=f"Job {request.job_id} not found in scraped data.",
        )

    # Run AI analysis
    try:
        analysis = await analyze_resume_job_fit(parsed, job)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI analysis failed: {str(e)}",
        )

    # Cache result
    await storage.save_ai_analysis(analysis)

    return analysis


@ats_router.get("/analyze/{resume_id}/{job_id}")
async def get_cached_analysis(resume_id: str, job_id: str):
    """Get cached AI analysis for a resume-job pair."""
    analysis = await storage.load_ai_analysis(resume_id, job_id)
    if not analysis:
        raise HTTPException(
            status_code=404,
            detail=f"No AI analysis found for resume {resume_id} and job {job_id}. "
            "Run POST /ats/analyze first.",
        )
    return analysis


# ---------------------------------------------------------------------------
# Keyword Gap (convenience endpoint)
# ---------------------------------------------------------------------------

@ats_router.get("/gaps/{resume_id}/{job_id}")
async def get_keyword_gaps(resume_id: str, job_id: str):
    """Get keyword gap analysis for a specific resume-job pair.

    Shows which skills are missing, present, and partially matched.
    """
    # Check if we have cached match results with this job
    cached = await storage.load_match_results(resume_id)
    if cached:
        for match in cached.matches:
            if match.job_id == job_id:
                return {
                    "resume_id": resume_id,
                    "job_id": job_id,
                    "job_title": match.job_title,
                    "company_name": match.company_name,
                    "overall_score": match.overall_score,
                    "keyword_gap": match.keyword_gap,
                }

    # No cached result -- compute on the fly
    parsed = await storage.load_parsed_resume(resume_id)
    if not parsed:
        raise HTTPException(status_code=404, detail=f"Resume {resume_id} not found")

    all_jobs = _load_scraped_jobs()
    job = _find_job_by_id(all_jobs, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    result = score_match(parsed, job)
    return {
        "resume_id": resume_id,
        "job_id": job_id,
        "job_title": result.job_title,
        "company_name": result.company_name,
        "overall_score": result.overall_score,
        "keyword_gap": result.keyword_gap,
    }
