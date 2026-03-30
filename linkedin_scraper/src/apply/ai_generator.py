"""
AI-powered content generation for the Auto-Apply module.
Uses xAI Grok API via OpenAI SDK for cover letters, answer generation,
resume tailoring, and fit summaries.
"""

import json
import os
from typing import Optional, List, Dict

from . import storage
from .models import (
    UserProfile,
    CoverLetterResponse,
    ResumeTailorResponse,
    AnswerResponse,
    FitSummaryResponse,
)

XAI_API_KEY = os.getenv("XAI_API_KEY")
XAI_BASE_URL = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1")
XAI_MODEL = os.getenv("XAI_MODEL", "grok-3-fast")


def _get_client():
    """Get OpenAI-compatible client for xAI Grok."""
    if not XAI_API_KEY:
        raise ValueError(
            "XAI_API_KEY environment variable is not set. "
            "Get an API key from https://console.x.ai/"
        )
    try:
        from openai import OpenAI
        return OpenAI(api_key=XAI_API_KEY, base_url=XAI_BASE_URL)
    except ImportError:
        raise ImportError(
            "The 'openai' package is required for AI generation. "
            "Install it with: pip install openai"
        )


def _chat(system_prompt: str, user_prompt: str, max_tokens: int = 1500) -> str:
    """Send a chat completion request and return the text response."""
    client = _get_client()
    response = client.chat.completions.create(
        model=XAI_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content.strip()


def _parse_json_response(text: str) -> dict:
    """Parse a JSON response, handling markdown code blocks."""
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1])

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group(0))
        raise ValueError(f"Failed to parse AI response as JSON: {text[:200]}")


# ---------------------------------------------------------------------------
# Cover Letter Generation
# ---------------------------------------------------------------------------

def generate_cover_letter(
    profile: UserProfile,
    job: dict,
    tone: str = "professional",
    max_words: int = 300,
) -> CoverLetterResponse:
    """Generate a tailored cover letter for a specific job."""
    user_id = profile.user_id
    job_id = str(job.get("job_id", ""))

    # Check cache
    cached = storage.load_text(storage.cover_letter_path(user_id, job_id))
    if cached:
        return CoverLetterResponse(
            job_id=job_id,
            job_title=job.get("title", "Unknown"),
            company_name=job.get("company_name", "Unknown"),
            cover_letter=cached,
            cached=True,
        )

    resume_text = profile.resume_text or ""
    resume_context = storage.load_text(storage.user_resume_text_path(user_id))
    if resume_context:
        resume_text = resume_context[:3000]

    system_prompt = f"""You are an expert career advisor. Write a concise, compelling cover letter.
Tone: {tone}. Maximum {max_words} words. Do not include placeholder brackets like [Company] — use the actual names provided."""

    user_prompt = f"""Write a cover letter for this job application.

APPLICANT:
Name: {profile.name or 'Not provided'}
Summary: {profile.summary or 'Not provided'}
Skills: {', '.join(profile.skills[:20]) if profile.skills else 'Not listed'}

Resume excerpt:
{resume_text[:2000]}

JOB:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company_name', 'Unknown')}
Location: {job.get('formatted_location', 'Not specified')}
Description: {(job.get('description') or '')[:1500]}
Required Skills: {job.get('skills_description', 'Not specified')}

Write the cover letter directly — no preamble, no sign-off instructions."""

    cover_letter = _chat(system_prompt, user_prompt, max_tokens=800)

    # Cache it
    storage.save_text(storage.cover_letter_path(user_id, job_id), cover_letter)

    return CoverLetterResponse(
        job_id=job_id,
        job_title=job.get("title", "Unknown"),
        company_name=job.get("company_name", "Unknown"),
        cover_letter=cover_letter,
        cached=False,
    )


# ---------------------------------------------------------------------------
# Resume Tailoring
# ---------------------------------------------------------------------------

def tailor_resume(profile: UserProfile, job: dict) -> ResumeTailorResponse:
    """Suggest resume bullet rewording to better match a job's keywords."""
    user_id = profile.user_id
    job_id = str(job.get("job_id", ""))

    # Check cache
    cached_data = storage.load_json(storage.resume_tailor_path(user_id, job_id))
    if cached_data:
        return ResumeTailorResponse(**cached_data)

    resume_text = profile.resume_text or ""
    resume_context = storage.load_text(storage.user_resume_text_path(user_id))
    if resume_context:
        resume_text = resume_context[:3000]

    system_prompt = """You are an ATS optimization expert. Analyze the resume against the job description and suggest specific bullet point rewording to improve keyword matching. Return JSON only."""

    user_prompt = f"""Compare this resume against the job posting and suggest improvements.

RESUME:
{resume_text[:2500]}

JOB:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company_name', 'Unknown')}
Required Skills: {job.get('skills_description', 'Not specified')}
Description: {(job.get('description') or '')[:1500]}

Return a JSON object:
{{
  "suggestions": [
    {{"original": "original bullet text", "suggested": "improved bullet text", "reason": "why this change helps ATS matching"}}
  ],
  "missing_keywords": ["keyword1", "keyword2"]
}}"""

    response_text = _chat(system_prompt, user_prompt, max_tokens=1500)
    data = _parse_json_response(response_text)

    result = ResumeTailorResponse(
        job_id=job_id,
        job_title=job.get("title", "Unknown"),
        company_name=job.get("company_name", "Unknown"),
        suggestions=data.get("suggestions", []),
        missing_keywords=data.get("missing_keywords", []),
    )

    # Cache it
    storage.save_json(storage.resume_tailor_path(user_id, job_id), result.model_dump())
    return result


# ---------------------------------------------------------------------------
# Application Question Answering
# ---------------------------------------------------------------------------

def answer_question(
    profile: UserProfile,
    job: dict,
    question: str,
) -> AnswerResponse:
    """Answer an application question. Checks common_answers first, then uses AI."""
    job_id = str(job.get("job_id", ""))

    # Check common answers first (case-insensitive fuzzy match)
    question_lower = question.lower().strip()
    for key, value in profile.common_answers.items():
        if key.lower() in question_lower or question_lower in key.lower():
            return AnswerResponse(
                job_id=job_id,
                question=question,
                answer=value,
                source="common_answers",
            )

    # Generate with AI
    resume_text = profile.resume_text or ""

    system_prompt = """You are helping someone answer a job application question.
Give a direct, professional answer based on the applicant's background.
Keep it concise (2-4 sentences max). Answer in first person."""

    user_prompt = f"""Answer this application question for the applicant.

APPLICANT:
Name: {profile.name or 'Not provided'}
Skills: {', '.join(profile.skills[:15]) if profile.skills else 'Not listed'}
Summary: {profile.summary or 'Not provided'}
Resume excerpt: {resume_text[:1000]}

JOB:
Title: {job.get('title', 'Unknown')} at {job.get('company_name', 'Unknown')}

QUESTION: {question}

Answer directly (no preamble):"""

    answer = _chat(system_prompt, user_prompt, max_tokens=300)

    return AnswerResponse(
        job_id=job_id,
        question=question,
        answer=answer,
        source="ai_generated",
    )


# ---------------------------------------------------------------------------
# Fit Summary
# ---------------------------------------------------------------------------

def generate_fit_summary(profile: UserProfile, job: dict) -> FitSummaryResponse:
    """Generate a one-paragraph analysis of job fit."""
    user_id = profile.user_id
    job_id = str(job.get("job_id", ""))

    # Check cache
    cached_data = storage.load_json(storage.fit_summary_path(user_id, job_id))
    if cached_data:
        return FitSummaryResponse(**cached_data)

    resume_text = profile.resume_text or ""
    resume_context = storage.load_text(storage.user_resume_text_path(user_id))
    if resume_context:
        resume_text = resume_context[:2000]

    system_prompt = """You are a career advisor. Analyze job fit and return JSON only."""

    user_prompt = f"""Analyze how well this applicant fits the job.

APPLICANT:
Skills: {', '.join(profile.skills[:20]) if profile.skills else 'Not listed'}
Target Roles: {', '.join(profile.target_roles) if profile.target_roles else 'Not specified'}
Summary: {profile.summary or 'Not provided'}
Resume excerpt: {resume_text[:1500]}

JOB:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company_name', 'Unknown')}
Location: {job.get('formatted_location', 'Not specified')}
Experience Level: {job.get('experience_level', 'Not specified')}
Skills: {job.get('skills_description', 'Not specified')}
Description: {(job.get('description') or '')[:1000]}

Return JSON:
{{
  "fit_score": <0-100>,
  "summary": "2-3 sentence fit assessment",
  "strengths": ["strength1", "strength2"],
  "concerns": ["concern1", "concern2"]
}}"""

    response_text = _chat(system_prompt, user_prompt, max_tokens=600)
    data = _parse_json_response(response_text)

    result = FitSummaryResponse(
        job_id=job_id,
        job_title=job.get("title", "Unknown"),
        company_name=job.get("company_name", "Unknown"),
        fit_score=float(data.get("fit_score", 50)),
        summary=data.get("summary", "Analysis completed"),
        strengths=data.get("strengths", []),
        concerns=data.get("concerns", []),
    )

    # Cache it
    storage.save_json(storage.fit_summary_path(user_id, job_id), result.model_dump())
    return result
