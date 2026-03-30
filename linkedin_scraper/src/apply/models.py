"""
Pydantic data models for the Auto-Apply module.
Reuses ATS models (ParsedResume, ContactInfo, etc.) where applicable.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# User Profile Models
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    user_id: str
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    target_companies: List[str] = Field(default_factory=list)
    blacklist_companies: List[str] = Field(default_factory=list)
    min_salary: Optional[int] = None
    preferred_locations: List[str] = Field(default_factory=list)
    preferred_workplace: List[str] = Field(default_factory=list)  # remote, hybrid, on_site
    preferred_experience_levels: List[str] = Field(default_factory=list)
    common_answers: Dict[str, str] = Field(default_factory=dict)
    resume_s3_key: Optional[str] = None
    resume_text: Optional[str] = None
    resume_id: Optional[str] = None  # Link to ATS parsed resume
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ProfileCreateRequest(BaseModel):
    email: str
    name: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    target_roles: List[str] = Field(default_factory=list)
    target_companies: List[str] = Field(default_factory=list)
    blacklist_companies: List[str] = Field(default_factory=list)
    min_salary: Optional[int] = None
    preferred_locations: List[str] = Field(default_factory=list)
    preferred_workplace: List[str] = Field(default_factory=list)
    preferred_experience_levels: List[str] = Field(default_factory=list)
    common_answers: Dict[str, str] = Field(default_factory=dict)


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    summary: Optional[str] = None
    skills: Optional[List[str]] = None
    target_roles: Optional[List[str]] = None
    target_companies: Optional[List[str]] = None
    blacklist_companies: Optional[List[str]] = None
    min_salary: Optional[int] = None
    preferred_locations: Optional[List[str]] = None
    preferred_workplace: Optional[List[str]] = None
    preferred_experience_levels: Optional[List[str]] = None
    common_answers: Optional[Dict[str, str]] = None


# ---------------------------------------------------------------------------
# Application Tracking Models
# ---------------------------------------------------------------------------

class ApplicationStatus(str, Enum):
    INTERESTED = "interested"
    PREPARING = "preparing"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class ApplicationEvent(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    event_type: str  # status_change, note_added, cover_letter_generated, etc.
    details: Optional[str] = None


class Application(BaseModel):
    user_id: str
    job_id: str
    status: ApplicationStatus = ApplicationStatus.INTERESTED
    applied_at: Optional[str] = None
    applied_via: Optional[str] = None  # easy_apply, company_site, manual
    cover_letter_s3_key: Optional[str] = None
    resume_version_s3_key: Optional[str] = None
    notes: Optional[str] = None
    follow_up_date: Optional[str] = None
    generated_answers: Dict[str, str] = Field(default_factory=dict)
    events: List[ApplicationEvent] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class ApplicationCreateRequest(BaseModel):
    job_id: str
    status: Optional[ApplicationStatus] = ApplicationStatus.INTERESTED
    notes: Optional[str] = None


class ApplicationUpdateRequest(BaseModel):
    status: Optional[ApplicationStatus] = None
    notes: Optional[str] = None
    follow_up_date: Optional[str] = None
    applied_via: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Generation Models
# ---------------------------------------------------------------------------

class CoverLetterRequest(BaseModel):
    job_id: str
    tone: Optional[str] = "professional"  # professional, casual, enthusiastic
    max_words: Optional[int] = 300


class CoverLetterResponse(BaseModel):
    job_id: str
    job_title: str
    company_name: str
    cover_letter: str
    cached: bool = False


class ResumeTailorRequest(BaseModel):
    job_id: str


class ResumeTailorResponse(BaseModel):
    job_id: str
    job_title: str
    company_name: str
    suggestions: List[Dict[str, str]]  # [{original, suggested, reason}]
    missing_keywords: List[str]


class AnswerRequest(BaseModel):
    job_id: str
    question: str


class AnswerResponse(BaseModel):
    job_id: str
    question: str
    answer: str
    source: str  # "common_answers" or "ai_generated"


class FitSummaryRequest(BaseModel):
    job_id: str


class FitSummaryResponse(BaseModel):
    job_id: str
    job_title: str
    company_name: str
    fit_score: float
    summary: str
    strengths: List[str]
    concerns: List[str]


# ---------------------------------------------------------------------------
# Job Scoring Models
# ---------------------------------------------------------------------------

class JobScoreBreakdown(BaseModel):
    skills_score: float = Field(ge=0, le=40)
    title_score: float = Field(ge=0, le=20)
    experience_level_score: float = Field(ge=0, le=15)
    location_score: float = Field(ge=0, le=10)
    salary_score: float = Field(ge=0, le=10)
    company_score: float = Field(ge=0, le=5)


class ScoredJob(BaseModel):
    job_id: str
    title: str
    company_name: str
    overall_score: float = Field(ge=0, le=100)
    breakdown: JobScoreBreakdown
    url: Optional[str] = None
    location: Optional[str] = None
    experience_level: Optional[str] = None
    workplace_type: Optional[str] = None
    salary: Optional[str] = None
    posted_dt: Optional[str] = None


# ---------------------------------------------------------------------------
# Auth Models
# ---------------------------------------------------------------------------

class APIKeyCreateRequest(BaseModel):
    email: str
    name: Optional[str] = None


class APIKeyResponse(BaseModel):
    api_key: str
    user_id: str
    email: str
    message: str
