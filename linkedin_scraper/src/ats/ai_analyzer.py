"""
Claude API integration for deep resume-job fit analysis.
Provides intelligent assessment, gap identification, and optimization suggestions.
"""

import json
import os
from typing import Optional

from .models import ParsedResume, AIAnalysisResult, OptimizationSuggestion


ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-20250514"


def _get_client():
    """Get Anthropic client. Raises if API key is not configured."""
    if not ANTHROPIC_API_KEY:
        raise ValueError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Set it in your .env file or environment to use AI analysis."
        )
    try:
        import anthropic
        return anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    except ImportError:
        raise ImportError(
            "The 'anthropic' package is required for AI analysis. "
            "Install it with: pip install anthropic"
        )


def _build_analysis_prompt(resume: ParsedResume, job: dict) -> str:
    """Build the analysis prompt for Claude."""

    # Format resume info
    resume_skills = ", ".join(resume.skills) if resume.skills else "None listed"
    resume_experience = ""
    for exp in resume.work_experience:
        resume_experience += f"\n  - {exp.title} at {exp.company}"
        if exp.start_date:
            resume_experience += f" ({exp.start_date} - {exp.end_date or 'Present'})"
        if exp.description:
            resume_experience += f"\n    {exp.description[:300]}"

    resume_education = ""
    for edu in resume.education:
        resume_education += f"\n  - {edu.degree or ''} {edu.field_of_study or ''} at {edu.institution}"
        if edu.graduation_date:
            resume_education += f" ({edu.graduation_date})"

    # Format job info
    job_skills = job.get("skills_description", "Not specified")
    job_education = job.get("education_description", "Not specified")
    job_functions = job.get("job_functions", [])
    if isinstance(job_functions, list):
        job_functions = ", ".join(job_functions)
    job_industries = job.get("formatted_industries") or job.get("industries", [])
    if isinstance(job_industries, list):
        job_industries = ", ".join(str(i) for i in job_industries)
    job_benefits = job.get("benefits", [])
    if isinstance(job_benefits, list):
        job_benefits = ", ".join(str(b) for b in job_benefits) if job_benefits else "Not specified"

    return f"""You are an expert ATS (Applicant Tracking System) analyst and career advisor. Analyze how well this resume matches the job posting below.

Return your analysis as a JSON object with this exact structure:
{{
  "overall_assessment": "1-2 sentence assessment of fit",
  "fit_score": <number 0-100>,
  "strengths": ["strength 1", "strength 2", ...],
  "weaknesses": ["weakness 1", "weakness 2", ...],
  "optimization_suggestions": [
    {{
      "category": "<skills|experience|keywords|formatting>",
      "priority": "<high|medium|low>",
      "suggestion": "what to change",
      "rationale": "why this matters for ATS"
    }}
  ],
  "rewritten_summary": "A tailored professional summary for this specific role (2-3 sentences)"
}}

RESUME:
Name: {resume.contact_info.name or 'Not provided'}
Summary: {resume.summary or 'Not provided'}
Skills: {resume_skills}
Experience:{resume_experience or ' None listed'}
Education:{resume_education or ' None listed'}
Certifications: {', '.join(resume.certifications) if resume.certifications else 'None'}

Full resume text:
{resume.raw_text[:3000]}

JOB POSTING:
Title: {job.get('title', 'Unknown')}
Company: {job.get('company_name', 'Unknown')}
Location: {job.get('formatted_location', 'Not specified')}
Experience Level: {job.get('experience_level', 'Not specified')}
Workplace Type: {job.get('workplace_type_label', 'Not specified')}
Required Skills: {job_skills}
Education Requirements: {job_education}
Job Functions: {job_functions}
Industry: {job_industries}
Benefits: {job_benefits}
Salary: {job.get('formatted_salary_description', 'Not specified')}

Return ONLY the JSON object, no additional text."""


async def analyze_resume_job_fit(
    resume: ParsedResume,
    job: dict,
) -> AIAnalysisResult:
    """Use Claude to perform deep analysis of resume-job fit.

    This is the premium analysis endpoint -- slower but much more nuanced
    than deterministic scoring.
    """
    client = _get_client()
    prompt = _build_analysis_prompt(resume, job)

    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    # Parse Claude's response
    response_text = message.content[0].text.strip()

    # Handle potential markdown code blocks
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        data = json.loads(response_text)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        import re
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            data = json.loads(json_match.group(0))
        else:
            raise ValueError(f"Failed to parse AI response as JSON: {response_text[:200]}")

    # Build result
    suggestions = []
    for s in data.get("optimization_suggestions", []):
        suggestions.append(
            OptimizationSuggestion(
                category=s.get("category", "general"),
                priority=s.get("priority", "medium"),
                suggestion=s.get("suggestion", ""),
                rationale=s.get("rationale", ""),
            )
        )

    return AIAnalysisResult(
        resume_id=resume.resume_id,
        job_id=str(job.get("job_id", "")),
        job_title=job.get("title", "Unknown"),
        company_name=job.get("company_name", "Unknown"),
        overall_assessment=data.get("overall_assessment", "Analysis completed"),
        fit_score=float(data.get("fit_score", 50)),
        strengths=data.get("strengths", []),
        weaknesses=data.get("weaknesses", []),
        optimization_suggestions=suggestions,
        rewritten_summary=data.get("rewritten_summary"),
    )


async def ai_parse_resume(raw_text: str) -> dict:
    """Use Claude to extract structured resume data from raw text.

    Returns a dict that can be used to enhance a ParsedResume.
    Useful for non-standard resume formats where regex parsing fails.
    """
    client = _get_client()

    prompt = f"""Parse this resume text into structured JSON with this format:
{{
  "name": "full name",
  "email": "email address",
  "phone": "phone number",
  "linkedin_url": "linkedin profile url",
  "location": "city, state",
  "summary": "professional summary",
  "skills": ["skill1", "skill2", ...],
  "work_experience": [
    {{
      "title": "job title",
      "company": "company name",
      "start_date": "start date",
      "end_date": "end date or Present",
      "description": "role description"
    }}
  ],
  "education": [
    {{
      "degree": "degree type",
      "field_of_study": "field",
      "institution": "school name",
      "graduation_date": "year"
    }}
  ],
  "certifications": ["cert1", "cert2", ...]
}}

RESUME TEXT:
{raw_text[:4000]}

Return ONLY the JSON object, no additional text."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        response_text = "\n".join(lines[1:-1])

    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        import re
        json_match = re.search(r"\{[\s\S]*\}", response_text)
        if json_match:
            return json.loads(json_match.group(0))
        raise ValueError("Failed to parse AI resume parsing response")
