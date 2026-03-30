"""
Deterministic match scoring engine.
Scores resume-job fit using weighted keyword overlap, experience relevance,
education matching, and keyword density analysis.
"""

import math
import re
from collections import Counter
from typing import List, Set, Dict, Optional

from .models import (
    ParsedResume,
    MatchResult,
    MatchScoreBreakdown,
    KeywordGap,
)
from .skill_extractor import extract_skills_from_text, extract_skills_from_job, normalize_skill


# ---------------------------------------------------------------------------
# Scoring Weights
# ---------------------------------------------------------------------------

WEIGHT_SKILLS = 0.40
WEIGHT_EXPERIENCE = 0.25
WEIGHT_EDUCATION = 0.15
WEIGHT_KEYWORDS = 0.20

# Stopwords for keyword density calculation
STOPWORDS: Set[str] = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "it", "as", "be", "was", "were",
    "are", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "can", "shall",
    "this", "that", "these", "those", "not", "no", "nor", "so", "if",
    "then", "than", "too", "very", "just", "about", "above", "after",
    "before", "between", "into", "through", "during", "each", "all",
    "both", "more", "most", "other", "some", "such", "only", "own",
    "same", "also", "how", "any", "our", "out", "up", "what", "which",
    "who", "when", "where", "why", "we", "you", "your", "they", "their",
    "its", "my", "me", "him", "her", "us", "them", "i", "he", "she",
    "able", "experience", "work", "working", "team", "role", "job",
    "company", "including", "using", "etc", "eg", "ie", "must", "need",
    "required", "preferred", "strong", "excellent", "good", "great",
    "well", "new", "years", "year", "knowledge", "understanding",
}


# ---------------------------------------------------------------------------
# Component Scorers
# ---------------------------------------------------------------------------

def compute_skills_score(resume_skills: List[str], job_skills: List[str]) -> float:
    """Compute skills overlap score (0-100) using Jaccard-like similarity.

    Uses normalized canonical skill names for comparison.
    Weighted toward recall (how many job skills the resume covers).
    """
    if not job_skills:
        return 50.0  # Neutral if job has no skill requirements

    resume_set = {s.lower() for s in resume_skills}
    job_set = {s.lower() for s in job_skills}

    if not resume_set:
        return 0.0

    # Recall: what fraction of job skills does the resume cover?
    matched = resume_set & job_set
    recall = len(matched) / len(job_set) if job_set else 0

    # Precision bonus: small bonus for having relevant skills
    precision = len(matched) / len(resume_set) if resume_set else 0

    # Weighted F-score favoring recall (beta=2)
    beta = 2.0
    if recall + precision == 0:
        return 0.0
    f_score = (1 + beta**2) * (precision * recall) / ((beta**2 * precision) + recall)

    return min(100.0, f_score * 100)


def compute_experience_score(resume: ParsedResume, job: dict) -> float:
    """Score experience relevance (0-100) based on title/description overlap and level match."""
    score = 0.0

    # 1. Title relevance (up to 50 points)
    job_title = (job.get("title") or "").lower()
    job_title_words = set(re.findall(r"\b\w{3,}\b", job_title)) - STOPWORDS

    if job_title_words and resume.work_experience:
        best_title_score = 0.0
        for exp in resume.work_experience:
            exp_title = exp.title.lower()
            exp_title_words = set(re.findall(r"\b\w{3,}\b", exp_title)) - STOPWORDS
            if exp_title_words:
                overlap = len(job_title_words & exp_title_words) / len(job_title_words)
                best_title_score = max(best_title_score, overlap)
        score += best_title_score * 50
    elif resume.work_experience:
        score += 20  # Has experience but can't compare titles

    # 2. Description keyword overlap (up to 30 points)
    job_desc_parts = []
    for field in ["skills_description", "company_description"]:
        if job.get(field):
            job_desc_parts.append(job[field])
    job_desc = " ".join(job_desc_parts).lower()
    job_desc_words = set(re.findall(r"\b\w{3,}\b", job_desc)) - STOPWORDS

    if job_desc_words and resume.work_experience:
        resume_exp_text = " ".join(
            (exp.description or "") + " " + exp.title
            for exp in resume.work_experience
        ).lower()
        resume_exp_words = set(re.findall(r"\b\w{3,}\b", resume_exp_text)) - STOPWORDS

        if resume_exp_words:
            overlap = len(job_desc_words & resume_exp_words) / len(job_desc_words)
            score += min(30.0, overlap * 60)

    # 3. Experience level alignment (up to 20 points)
    job_level = (job.get("experience_level") or "").lower()
    if job_level and resume.work_experience:
        num_roles = len(resume.work_experience)
        level_score = _estimate_level_fit(num_roles, job_level)
        score += level_score * 20

    return min(100.0, score)


def _estimate_level_fit(num_roles: int, job_level: str) -> float:
    """Estimate how well the number of past roles fits the expected level."""
    level_expectations = {
        "intern": (0, 1),
        "entry": (0, 2),
        "associate": (1, 3),
        "mid-senior": (2, 6),
        "director": (4, 10),
        "executive": (5, 15),
    }
    expected_min, expected_max = level_expectations.get(job_level, (0, 10))

    if expected_min <= num_roles <= expected_max:
        return 1.0
    elif num_roles < expected_min:
        return max(0.3, num_roles / expected_min) if expected_min > 0 else 0.5
    else:
        # Overqualified is better than underqualified
        return max(0.5, 1.0 - (num_roles - expected_max) * 0.1)


def compute_education_score(resume: ParsedResume, job: dict) -> float:
    """Score education match (0-100) based on degree level and field relevance."""
    edu_desc = (job.get("education_description") or "").lower()
    if not edu_desc:
        return 60.0  # Neutral if no education requirements

    if not resume.education:
        return 20.0  # Has requirements but resume has no education listed

    score = 0.0

    # Degree level matching (up to 60 points)
    degree_levels = {
        "phd": 5, "doctoral": 5, "doctorate": 5,
        "master": 4, "mba": 4, "ms": 4, "ma": 4,
        "bachelor": 3, "bs": 3, "ba": 3,
        "associate": 2,
        "diploma": 1, "certificate": 1,
    }

    # Find highest required degree from job
    required_level = 0
    for keyword, level in degree_levels.items():
        if keyword in edu_desc:
            required_level = max(required_level, level)

    # Find highest resume degree
    resume_level = 0
    for edu in resume.education:
        degree_text = ((edu.degree or "") + " " + (edu.field_of_study or "")).lower()
        for keyword, level in degree_levels.items():
            if keyword in degree_text:
                resume_level = max(resume_level, level)

    if required_level == 0:
        score += 40.0  # No specific level required
    elif resume_level >= required_level:
        score += 60.0
    elif resume_level == required_level - 1:
        score += 40.0  # Close enough
    else:
        score += 15.0

    # Field relevance (up to 40 points)
    edu_keywords = set(re.findall(r"\b\w{4,}\b", edu_desc)) - STOPWORDS
    if edu_keywords:
        resume_edu_text = " ".join(
            (e.field_of_study or "") + " " + (e.degree or "") + " " + e.institution
            for e in resume.education
        ).lower()
        resume_edu_words = set(re.findall(r"\b\w{4,}\b", resume_edu_text)) - STOPWORDS

        if resume_edu_words:
            overlap = len(edu_keywords & resume_edu_words) / len(edu_keywords)
            score += overlap * 40
        else:
            score += 10.0
    else:
        score += 25.0

    return min(100.0, score)


def compute_keyword_density(resume_text: str, job: dict) -> float:
    """Score keyword presence (0-100) based on how many significant job terms
    appear anywhere in the resume text."""
    # Build job keyword set from multiple fields
    job_parts = []
    for field in ["title", "skills_description", "education_description", "company_description"]:
        if job.get(field):
            job_parts.append(str(job[field]))
    if job.get("job_functions") and isinstance(job["job_functions"], list):
        job_parts.extend(job["job_functions"])

    job_text = " ".join(job_parts).lower()
    job_words = set(re.findall(r"\b\w{3,}\b", job_text)) - STOPWORDS

    if not job_words:
        return 50.0

    resume_lower = resume_text.lower()
    resume_words = set(re.findall(r"\b\w{3,}\b", resume_lower)) - STOPWORDS

    if not resume_words:
        return 0.0

    matched = job_words & resume_words
    coverage = len(matched) / len(job_words)

    return min(100.0, coverage * 100)


# ---------------------------------------------------------------------------
# Keyword Gap Analysis
# ---------------------------------------------------------------------------

def compute_keyword_gap(resume_skills: List[str], job_skills: List[str]) -> KeywordGap:
    """Identify which job skills are present, missing, or partially matched in the resume."""
    resume_set = {s.lower() for s in resume_skills}
    resume_originals = {s.lower(): s for s in resume_skills}

    missing = []
    present = []
    partial = []

    for job_skill in job_skills:
        job_lower = job_skill.lower()
        if job_lower in resume_set:
            present.append(job_skill)
        else:
            # Check for partial matches (substring or close)
            found_partial = False
            for resume_skill in resume_skills:
                r_lower = resume_skill.lower()
                if job_lower in r_lower or r_lower in job_lower:
                    partial.append({
                        "job_term": job_skill,
                        "resume_term": resume_skill,
                    })
                    found_partial = True
                    break
            if not found_partial:
                missing.append(job_skill)

    return KeywordGap(
        missing_keywords=sorted(missing),
        present_keywords=sorted(present),
        partial_matches=partial,
    )


# ---------------------------------------------------------------------------
# Main Scoring Functions
# ---------------------------------------------------------------------------

def score_match(resume: ParsedResume, job: dict) -> MatchResult:
    """Score a single resume-job pair. Returns a full MatchResult."""
    # Extract skills from both sides
    resume_skills = extract_skills_from_text(resume.raw_text)
    # Also include explicitly listed skills from the resume
    all_resume_skills = list(set(resume_skills + [normalize_skill(s) for s in resume.skills]))

    job_skills = extract_skills_from_job(job)

    # Compute component scores
    skills_score = compute_skills_score(all_resume_skills, job_skills)
    experience_score = compute_experience_score(resume, job)
    education_score = compute_education_score(resume, job)
    keyword_density_score = compute_keyword_density(resume.raw_text, job)

    # Weighted overall score
    overall = (
        skills_score * WEIGHT_SKILLS
        + experience_score * WEIGHT_EXPERIENCE
        + education_score * WEIGHT_EDUCATION
        + keyword_density_score * WEIGHT_KEYWORDS
    )

    breakdown = MatchScoreBreakdown(
        skills_score=round(skills_score, 1),
        experience_score=round(experience_score, 1),
        education_score=round(education_score, 1),
        keyword_density_score=round(keyword_density_score, 1),
    )

    keyword_gap = compute_keyword_gap(all_resume_skills, job_skills)

    return MatchResult(
        job_id=str(job.get("job_id", "")),
        job_title=job.get("title", "Unknown"),
        company_name=job.get("company_name", "Unknown"),
        overall_score=round(overall, 1),
        breakdown=breakdown,
        keyword_gap=keyword_gap,
        job_url=job.get("url"),
        location=job.get("formatted_location"),
        experience_level=job.get("experience_level"),
    )


def batch_score(
    resume: ParsedResume,
    jobs: List[dict],
    top_n: int = 10,
    min_score: float = 0.0,
) -> List[MatchResult]:
    """Score a resume against multiple jobs. Returns top N matches sorted by score."""
    results = []
    for job in jobs:
        try:
            result = score_match(resume, job)
            if result.overall_score >= min_score:
                results.append(result)
        except Exception as e:
            print(f"Warning: scoring failed for job {job.get('job_id')}: {e}")
            continue

    # Sort by overall score descending
    results.sort(key=lambda r: r.overall_score, reverse=True)

    return results[:top_n]
