"""
S3/local storage helpers for the Auto-Apply module.
Handles resume files, cover letters, and generated content.
Follows the same pattern as ats/storage.py.
"""

import json
import os
from typing import Optional

JOBS_BUCKET = os.getenv("JOBS_BUCKET")
LOCAL_STORAGE_DIR = os.getenv("APPLY_STORAGE_DIR", "/tmp/apply_data")


def _s3_client():
    """Get an S3 client, or None if unavailable."""
    if not JOBS_BUCKET:
        return None
    try:
        import boto3
        return boto3.client("s3")
    except Exception:
        return None


def _ensure_dir(path: str):
    """Ensure directory exists."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


# ---------------------------------------------------------------------------
# Generic S3/local operations
# ---------------------------------------------------------------------------

def save_blob(s3_key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Save binary data to S3 and local. Returns the S3 key."""
    # Save locally
    local_path = os.path.join(LOCAL_STORAGE_DIR, s3_key)
    _ensure_dir(local_path)
    with open(local_path, "wb") as f:
        f.write(data)

    # Upload to S3
    s3 = _s3_client()
    if s3:
        try:
            full_key = f"apply/{s3_key}"
            s3.put_object(Bucket=JOBS_BUCKET, Key=full_key, Body=data, ContentType=content_type)
            return full_key
        except Exception as e:
            print(f"Warning: S3 upload failed for {s3_key}: {e}")

    return s3_key


def save_json(s3_key: str, data: dict) -> str:
    """Save JSON data to S3 and local."""
    content = json.dumps(data, indent=2, default=str)
    return save_blob(s3_key, content.encode("utf-8"), "application/json")


def load_blob(s3_key: str) -> Optional[bytes]:
    """Load binary data. Tries local first, then S3."""
    # Try local
    local_path = os.path.join(LOCAL_STORAGE_DIR, s3_key)
    if os.path.exists(local_path):
        with open(local_path, "rb") as f:
            return f.read()

    # Try S3
    s3 = _s3_client()
    if s3:
        try:
            full_key = f"apply/{s3_key}"
            obj = s3.get_object(Bucket=JOBS_BUCKET, Key=full_key)
            return obj["Body"].read()
        except Exception:
            pass

    return None


def load_json(s3_key: str) -> Optional[dict]:
    """Load JSON data."""
    data = load_blob(s3_key)
    if data:
        return json.loads(data.decode("utf-8"))
    return None


def save_text(s3_key: str, text: str) -> str:
    """Save text data."""
    return save_blob(s3_key, text.encode("utf-8"), "text/plain")


def load_text(s3_key: str) -> Optional[str]:
    """Load text data."""
    data = load_blob(s3_key)
    if data:
        return data.decode("utf-8")
    return None


# ---------------------------------------------------------------------------
# User-specific paths
# ---------------------------------------------------------------------------

def user_resume_path(user_id: str, ext: str = "pdf") -> str:
    return f"profiles/{user_id}/resume.{ext}"


def user_resume_text_path(user_id: str) -> str:
    return f"profiles/{user_id}/resume_text.txt"


def cover_letter_path(user_id: str, job_id: str) -> str:
    return f"applications/{user_id}/{job_id}/cover_letter.txt"


def answers_path(user_id: str, job_id: str) -> str:
    return f"applications/{user_id}/{job_id}/answers.json"


def fit_summary_path(user_id: str, job_id: str) -> str:
    return f"applications/{user_id}/{job_id}/fit_summary.json"


def resume_tailor_path(user_id: str, job_id: str) -> str:
    return f"applications/{user_id}/{job_id}/resume_tailor.json"
