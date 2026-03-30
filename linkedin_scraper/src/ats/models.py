"""
Pydantic data models for the ATS Resume Analyzer.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum


# ---------------------------------------------------------------------------
# Resume Models
# ---------------------------------------------------------------------------

class ContactInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None


class WorkExperience(BaseModel):
    title: str
    company: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None  # None means "Present"
    description: Optional[str] = None
    skills_used: List[str] = Field(default_factory=list)


class Education(BaseModel):
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    institution: str
    graduation_date: Optional[str] = None
    gpa: Optional[str] = None


class ParsedResume(BaseModel):
    resume_id: str
    filename: str
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    summary: Optional[str] = None
    skills: List[str] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    raw_text: str = ""
    parsed_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    parse_method: str = "rule_based"


# ---------------------------------------------------------------------------
# Matching / Scoring Models
# ---------------------------------------------------------------------------

class MatchScoreBreakdown(BaseModel):
    skills_score: float = Field(ge=0, le=100, description="Skills keyword overlap score")
    experience_score: float = Field(ge=0, le=100, description="Experience relevance score")
    education_score: float = Field(ge=0, le=100, description="Education match score")
    keyword_density_score: float = Field(ge=0, le=100, description="Overall keyword presence in resume")


class KeywordGap(BaseModel):
    missing_keywords: List[str] = Field(default_factory=list)
    present_keywords: List[str] = Field(default_factory=list)
    partial_matches: List[Dict[str, str]] = Field(default_factory=list)


class MatchResult(BaseModel):
    job_id: str
    job_title: str
    company_name: str
    overall_score: float = Field(ge=0, le=100)
    breakdown: MatchScoreBreakdown
    keyword_gap: KeywordGap
    job_url: Optional[str] = None
    location: Optional[str] = None
    experience_level: Optional[str] = None
    matched_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# AI Analysis Models
# ---------------------------------------------------------------------------

class OptimizationSuggestion(BaseModel):
    category: str  # "skills", "experience", "keywords", "formatting"
    priority: str  # "high", "medium", "low"
    suggestion: str
    rationale: str


class AIAnalysisResult(BaseModel):
    resume_id: str
    job_id: str
    job_title: str
    company_name: str
    overall_assessment: str
    fit_score: float = Field(ge=0, le=100)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    optimization_suggestions: List[OptimizationSuggestion] = Field(default_factory=list)
    rewritten_summary: Optional[str] = None
    analyzed_at: str = Field(default_factory=lambda: datetime.now().isoformat())


# ---------------------------------------------------------------------------
# API Request / Response Models
# ---------------------------------------------------------------------------

class ResumeUploadResponse(BaseModel):
    resume_id: str
    filename: str
    status: str
    skills_found: int
    experience_count: int
    education_count: int
    message: str


class MatchRequest(BaseModel):
    resume_id: str
    job_ids: Optional[List[str]] = None  # None = match against all recent jobs
    top_n: Optional[int] = 10
    min_score: Optional[float] = 0.0


class BatchMatchResponse(BaseModel):
    resume_id: str
    total_jobs_compared: int
    matches: List[MatchResult]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class AIAnalysisRequest(BaseModel):
    resume_id: str
    job_id: str


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
