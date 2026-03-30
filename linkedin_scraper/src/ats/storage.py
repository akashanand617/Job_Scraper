"""
Storage layer for ATS resumes and analysis results.
Uses S3 when available (Lambda/production), falls back to local /tmp/ storage.
"""

import json
import os
import shutil
from typing import Optional, List, Dict

from .models import ParsedResume, BatchMatchResponse, AIAnalysisResult

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LOCAL_STORAGE_DIR = os.getenv("ATS_STORAGE_DIR", "/tmp/ats_data")
JOBS_BUCKET = os.getenv("JOBS_BUCKET")
MAX_FILE_SIZE_MB = 5


def _ensure_local_dirs():
    """Create local storage directories if they don't exist."""
    os.makedirs(os.path.join(LOCAL_STORAGE_DIR, "resumes"), exist_ok=True)
    os.makedirs(os.path.join(LOCAL_STORAGE_DIR, "analyses"), exist_ok=True)


def _s3_client():
    """Get an S3 client, or None if boto3/bucket unavailable."""
    if not JOBS_BUCKET:
        return None
    try:
        import boto3
        return boto3.client("s3")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Resume Storage
# ---------------------------------------------------------------------------

async def save_resume_file(resume_id: str, filename: str, file_bytes: bytes) -> str:
    """Save the original uploaded resume file. Returns the storage path."""
    _ensure_local_dirs()
    resume_dir = os.path.join(LOCAL_STORAGE_DIR, "resumes", resume_id)
    os.makedirs(resume_dir, exist_ok=True)

    ext = os.path.splitext(filename)[1].lower()
    local_path = os.path.join(resume_dir, f"original{ext}")
    with open(local_path, "wb") as f:
        f.write(file_bytes)

    # Upload to S3 if available
    s3 = _s3_client()
    if s3:
        try:
            s3_key = f"ats/resumes/{resume_id}/original{ext}"
            s3.put_object(Bucket=JOBS_BUCKET, Key=s3_key, Body=file_bytes)
        except Exception as e:
            print(f"Warning: S3 upload failed for resume {resume_id}: {e}")

    return local_path


async def save_parsed_resume(resume: ParsedResume) -> None:
    """Save the parsed resume JSON."""
    _ensure_local_dirs()
    resume_dir = os.path.join(LOCAL_STORAGE_DIR, "resumes", resume.resume_id)
    os.makedirs(resume_dir, exist_ok=True)

    local_path = os.path.join(resume_dir, "parsed.json")
    with open(local_path, "w") as f:
        f.write(resume.model_dump_json(indent=2))

    s3 = _s3_client()
    if s3:
        try:
            s3_key = f"ats/resumes/{resume.resume_id}/parsed.json"
            s3.put_object(
                Bucket=JOBS_BUCKET,
                Key=s3_key,
                Body=resume.model_dump_json(indent=2),
                ContentType="application/json",
            )
        except Exception as e:
            print(f"Warning: S3 upload failed for parsed resume {resume.resume_id}: {e}")


async def load_parsed_resume(resume_id: str) -> Optional[ParsedResume]:
    """Load a parsed resume by ID. Tries local first, then S3."""
    local_path = os.path.join(LOCAL_STORAGE_DIR, "resumes", resume_id, "parsed.json")
    if os.path.exists(local_path):
        with open(local_path, "r") as f:
            return ParsedResume.model_validate_json(f.read())

    s3 = _s3_client()
    if s3:
        try:
            s3_key = f"ats/resumes/{resume_id}/parsed.json"
            obj = s3.get_object(Bucket=JOBS_BUCKET, Key=s3_key)
            data = obj["Body"].read().decode("utf-8")
            return ParsedResume.model_validate_json(data)
        except Exception:
            pass

    return None


async def list_resumes() -> List[Dict]:
    """List all uploaded resumes with basic metadata."""
    _ensure_local_dirs()
    resumes = []
    resumes_dir = os.path.join(LOCAL_STORAGE_DIR, "resumes")

    if os.path.exists(resumes_dir):
        for resume_id in os.listdir(resumes_dir):
            parsed_path = os.path.join(resumes_dir, resume_id, "parsed.json")
            if os.path.exists(parsed_path):
                try:
                    with open(parsed_path, "r") as f:
                        data = json.load(f)
                    resumes.append({
                        "resume_id": data.get("resume_id", resume_id),
                        "filename": data.get("filename", "unknown"),
                        "skills_count": len(data.get("skills", [])),
                        "experience_count": len(data.get("work_experience", [])),
                        "parsed_at": data.get("parsed_at", ""),
                    })
                except Exception:
                    continue

    return resumes


async def delete_resume(resume_id: str) -> bool:
    """Delete a resume and all its associated data."""
    deleted = False

    # Delete local
    resume_dir = os.path.join(LOCAL_STORAGE_DIR, "resumes", resume_id)
    if os.path.exists(resume_dir):
        shutil.rmtree(resume_dir)
        deleted = True

    analysis_dir = os.path.join(LOCAL_STORAGE_DIR, "analyses", resume_id)
    if os.path.exists(analysis_dir):
        shutil.rmtree(analysis_dir)

    # Delete from S3
    s3 = _s3_client()
    if s3:
        try:
            for prefix in [f"ats/resumes/{resume_id}/", f"ats/analyses/{resume_id}/"]:
                response = s3.list_objects_v2(Bucket=JOBS_BUCKET, Prefix=prefix)
                if "Contents" in response:
                    for obj in response["Contents"]:
                        s3.delete_object(Bucket=JOBS_BUCKET, Key=obj["Key"])
                    deleted = True
        except Exception as e:
            print(f"Warning: S3 delete failed for resume {resume_id}: {e}")

    return deleted


# ---------------------------------------------------------------------------
# Match Results Storage
# ---------------------------------------------------------------------------

async def save_match_results(resume_id: str, results: BatchMatchResponse) -> None:
    """Save batch match results."""
    _ensure_local_dirs()
    analysis_dir = os.path.join(LOCAL_STORAGE_DIR, "analyses", resume_id)
    os.makedirs(analysis_dir, exist_ok=True)

    local_path = os.path.join(analysis_dir, "match_results.json")
    with open(local_path, "w") as f:
        f.write(results.model_dump_json(indent=2))

    s3 = _s3_client()
    if s3:
        try:
            s3_key = f"ats/analyses/{resume_id}/match_results.json"
            s3.put_object(
                Bucket=JOBS_BUCKET,
                Key=s3_key,
                Body=results.model_dump_json(indent=2),
                ContentType="application/json",
            )
        except Exception as e:
            print(f"Warning: S3 upload failed for match results {resume_id}: {e}")


async def load_match_results(resume_id: str) -> Optional[BatchMatchResponse]:
    """Load cached match results for a resume."""
    local_path = os.path.join(LOCAL_STORAGE_DIR, "analyses", resume_id, "match_results.json")
    if os.path.exists(local_path):
        with open(local_path, "r") as f:
            return BatchMatchResponse.model_validate_json(f.read())

    s3 = _s3_client()
    if s3:
        try:
            s3_key = f"ats/analyses/{resume_id}/match_results.json"
            obj = s3.get_object(Bucket=JOBS_BUCKET, Key=s3_key)
            data = obj["Body"].read().decode("utf-8")
            return BatchMatchResponse.model_validate_json(data)
        except Exception:
            pass

    return None


# ---------------------------------------------------------------------------
# AI Analysis Storage
# ---------------------------------------------------------------------------

async def save_ai_analysis(analysis: AIAnalysisResult) -> None:
    """Save AI analysis result for a specific resume-job pair."""
    _ensure_local_dirs()
    analysis_dir = os.path.join(LOCAL_STORAGE_DIR, "analyses", analysis.resume_id)
    os.makedirs(analysis_dir, exist_ok=True)

    local_path = os.path.join(analysis_dir, f"ai_{analysis.job_id}.json")
    with open(local_path, "w") as f:
        f.write(analysis.model_dump_json(indent=2))

    s3 = _s3_client()
    if s3:
        try:
            s3_key = f"ats/analyses/{analysis.resume_id}/ai_{analysis.job_id}.json"
            s3.put_object(
                Bucket=JOBS_BUCKET,
                Key=s3_key,
                Body=analysis.model_dump_json(indent=2),
                ContentType="application/json",
            )
        except Exception as e:
            print(f"Warning: S3 upload failed for AI analysis: {e}")


async def load_ai_analysis(resume_id: str, job_id: str) -> Optional[AIAnalysisResult]:
    """Load cached AI analysis for a resume-job pair."""
    local_path = os.path.join(LOCAL_STORAGE_DIR, "analyses", resume_id, f"ai_{job_id}.json")
    if os.path.exists(local_path):
        with open(local_path, "r") as f:
            return AIAnalysisResult.model_validate_json(f.read())

    s3 = _s3_client()
    if s3:
        try:
            s3_key = f"ats/analyses/{resume_id}/ai_{job_id}.json"
            obj = s3.get_object(Bucket=JOBS_BUCKET, Key=s3_key)
            data = obj["Body"].read().decode("utf-8")
            return AIAnalysisResult.model_validate_json(data)
        except Exception:
            pass

    return None
