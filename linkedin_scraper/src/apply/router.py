"""
FastAPI router for all Auto-Apply endpoints.
Mounted on the main app at /apply prefix.
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from typing import Optional

from .auth import require_auth, create_api_key
from .models import (
    ProfileCreateRequest,
    ProfileUpdateRequest,
    APIKeyCreateRequest,
    APIKeyResponse,
    ApplicationCreateRequest,
    ApplicationUpdateRequest,
    CoverLetterRequest,
    ResumeTailorRequest,
    AnswerRequest,
    FitSummaryRequest,
)
from .user_profile import UserProfileManager
from .job_matcher import JobMatcher
from .application_tracker import ApplicationTracker
from . import ai_generator

apply_router = APIRouter(prefix="/apply", tags=["Auto-Apply"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

# Singletons
_profile_manager = UserProfileManager()
_tracker = ApplicationTracker()


# ---------------------------------------------------------------------------
# Helper: load jobs from the scraper's data store
# ---------------------------------------------------------------------------

def _load_scraped_jobs():
    """Load jobs using the existing scraper data pipeline."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from simple_api import read_s3_hourly_batches_or_local_analytics
    return read_s3_hourly_batches_or_local_analytics()


def _find_job_by_id(jobs, job_id: str) -> Optional[dict]:
    for job in jobs:
        if str(job.get("job_id")) == str(job_id):
            return job
    return None


def _require_profile(user: dict):
    """Helper to load profile or raise 404."""
    profile = _profile_manager.get_profile(user["user_id"])
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile not found. Create one with POST /apply/profile first.",
        )
    return profile


def _require_job(job_id: str):
    """Helper to load a job or raise 404."""
    jobs = _load_scraped_jobs()
    job = _find_job_by_id(jobs, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found in scraped data.")
    return job


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@apply_router.post("/auth/register", response_model=APIKeyResponse)
async def register(request: APIKeyCreateRequest):
    """Register a new user and get an API key."""
    result = create_api_key(request.email, request.name)
    return APIKeyResponse(**result)


# ---------------------------------------------------------------------------
# Profile Management
# ---------------------------------------------------------------------------

@apply_router.post("/profile")
async def create_or_update_profile(
    request: ProfileCreateRequest,
    user: dict = Depends(require_auth),
):
    """Create or update user profile."""
    existing = _profile_manager.get_profile(user["user_id"])
    if existing:
        update = ProfileUpdateRequest(**request.model_dump(exclude={"email"}))
        profile = _profile_manager.update_profile(user["user_id"], update)
    else:
        profile = _profile_manager.create_profile(user["user_id"], request)
    return profile


@apply_router.get("/profile")
async def get_profile(user: dict = Depends(require_auth)):
    """Get current user's profile."""
    profile = _require_profile(user)
    return profile


@apply_router.delete("/profile")
async def delete_profile(user: dict = Depends(require_auth)):
    """Delete current user's profile."""
    deleted = _profile_manager.delete_profile(user["user_id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return {"message": "Profile deleted"}


@apply_router.post("/profile/resume")
async def upload_resume(
    file: UploadFile = File(...),
    user: dict = Depends(require_auth),
):
    """Upload a resume PDF/DOCX. Parses and links to the user profile."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("pdf", "docx", "doc"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: .{ext}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")
    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty")

    # Ensure profile exists
    _require_profile(user)

    result = await _profile_manager.upload_resume(user["user_id"], file.filename, file_bytes)
    return result


# ---------------------------------------------------------------------------
# Job Scoring
# ---------------------------------------------------------------------------

@apply_router.get("/jobs/scored")
async def get_scored_jobs(
    min_score: float = Query(0.0, ge=0, le=100),
    top_n: Optional[int] = Query(50, ge=1, le=500),
    user: dict = Depends(require_auth),
):
    """Score all scraped jobs against the user's profile. Returns ranked list."""
    profile = _require_profile(user)

    jobs = _load_scraped_jobs()
    if not jobs:
        raise HTTPException(status_code=404, detail="No scraped jobs available.")

    matcher = JobMatcher(profile)
    scored = matcher.score_all(jobs, min_score=min_score, top_n=top_n)

    return {
        "total_jobs_scored": len(jobs),
        "results_returned": len(scored),
        "min_score": min_score,
        "scored_jobs": [s.model_dump() for s in scored],
    }


@apply_router.get("/jobs/{job_id}/score")
async def score_single_job(
    job_id: str,
    user: dict = Depends(require_auth),
):
    """Score a specific job against the user's profile with full breakdown."""
    profile = _require_profile(user)
    job = _require_job(job_id)

    matcher = JobMatcher(profile)
    scored = matcher.score_job(job)
    return scored


# ---------------------------------------------------------------------------
# AI Generation
# ---------------------------------------------------------------------------

@apply_router.post("/generate/cover-letter")
async def gen_cover_letter(
    request: CoverLetterRequest,
    user: dict = Depends(require_auth),
):
    """Generate an AI-tailored cover letter for a specific job."""
    profile = _require_profile(user)
    job = _require_job(request.job_id)
    return ai_generator.generate_cover_letter(profile, job, request.tone, request.max_words)


@apply_router.post("/generate/resume-tailor")
async def gen_resume_tailor(
    request: ResumeTailorRequest,
    user: dict = Depends(require_auth),
):
    """Get AI suggestions for tailoring resume bullets to a specific job."""
    profile = _require_profile(user)
    job = _require_job(request.job_id)
    return ai_generator.tailor_resume(profile, job)


@apply_router.post("/generate/answer")
async def gen_answer(
    request: AnswerRequest,
    user: dict = Depends(require_auth),
):
    """Answer an application question using profile data and AI."""
    profile = _require_profile(user)
    job = _require_job(request.job_id)
    return ai_generator.answer_question(profile, job, request.question)


@apply_router.post("/generate/fit-summary")
async def gen_fit_summary(
    request: FitSummaryRequest,
    user: dict = Depends(require_auth),
):
    """Generate an AI-powered fit summary for a specific job."""
    profile = _require_profile(user)
    job = _require_job(request.job_id)
    return ai_generator.generate_fit_summary(profile, job)


# ---------------------------------------------------------------------------
# Application Tracking
# ---------------------------------------------------------------------------

@apply_router.get("/applications")
async def list_applications(
    status: Optional[str] = Query(None),
    user: dict = Depends(require_auth),
):
    """List all tracked applications, optionally filtered by status."""
    apps = _tracker.list_for_user(user["user_id"], status=status)
    return {
        "total": len(apps),
        "applications": [a.model_dump() for a in apps],
    }


@apply_router.post("/applications")
async def create_application(
    request: ApplicationCreateRequest,
    user: dict = Depends(require_auth),
):
    """Start tracking a job application."""
    # Verify job exists
    _require_job(request.job_id)

    existing = _tracker.get(user["user_id"], request.job_id)
    if existing:
        raise HTTPException(status_code=409, detail="Application already tracked for this job")

    app = _tracker.create(user["user_id"], request)
    return app


@apply_router.patch("/applications/{job_id}")
async def update_application(
    job_id: str,
    request: ApplicationUpdateRequest,
    user: dict = Depends(require_auth),
):
    """Update a tracked application (status, notes, follow-up date)."""
    app = _tracker.update(user["user_id"], job_id, request)
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


@apply_router.delete("/applications/{job_id}")
async def delete_application(
    job_id: str,
    user: dict = Depends(require_auth),
):
    """Stop tracking an application."""
    deleted = _tracker.delete(user["user_id"], job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"message": "Application tracking removed"}


@apply_router.get("/applications/stats")
async def get_application_stats(user: dict = Depends(require_auth)):
    """Get application statistics (counts, response rate, etc.)."""
    return _tracker.get_stats(user["user_id"])
