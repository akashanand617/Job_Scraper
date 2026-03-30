"""
Lightweight API key authentication for the Auto-Apply module.
Each user gets a UUID API key stored in DynamoDB (or local fallback).
"""

import uuid
from datetime import datetime
from typing import Optional

from fastapi import Header, HTTPException

from . import db


def create_api_key(email: str, name: Optional[str] = None) -> dict:
    """Create a new API key for a user. Returns {api_key, user_id, email}."""
    # Check if email already has a key
    existing = db.scan_items(db.USERS_TABLE)
    for user in existing:
        if user.get("email") == email:
            return {
                "api_key": user["api_key"],
                "user_id": user["user_id"],
                "email": email,
                "message": "API key already exists for this email",
            }

    api_key = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    item = {
        "api_key": api_key,
        "user_id": user_id,
        "email": email,
        "name": name or "",
        "created_at": datetime.now().isoformat(),
    }
    db.put_item(db.USERS_TABLE, item)

    return {
        "api_key": api_key,
        "user_id": user_id,
        "email": email,
        "message": "API key created successfully",
    }


def get_user_by_key(api_key: str) -> Optional[dict]:
    """Look up a user by API key. Returns user dict or None."""
    return db.get_item(db.USERS_TABLE, {"api_key": api_key})


async def require_auth(authorization: str = Header(..., description="Bearer <api_key>")) -> dict:
    """FastAPI dependency that extracts and validates the API key.

    Usage in endpoints:
        @router.get("/profile")
        async def get_profile(user: dict = Depends(require_auth)):
            user_id = user["user_id"]
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")

    # Accept both "Bearer <key>" and raw "<key>"
    token = authorization
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        raise HTTPException(status_code=401, detail="API key required")

    user = get_user_by_key(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return user
