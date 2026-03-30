"""
Company Ranker — the central engine that combines all scoring signals
into a composite score and assigns tiers to companies.

Scoring pipeline:
  1. Curated list membership (0-100)
  2. Funding / company scale from web enrichment (0-100)
  3. NLP relevance from transformer analysis (0-100)
  4. Job quality from scraped job data (0-100)
  5. Industry alignment (0-100)

Each signal is weighted per SCORING_WEIGHTS, producing a composite 0-100 score
that maps to a tier (T1_ELITE → T5_UNRANKED).
"""

import json
import os
import re
from datetime import datetime
from typing import Optional

from .tier_config import (
    TIER_THRESHOLDS,
    TIER_LABELS,
    SCORING_WEIGHTS,
    CURATED_LOOKUP,
    FUNDING_SCORE_BRACKETS,
    EMPLOYEE_SCORE_BRACKETS,
    SALARY_SCORE_BRACKETS,
    HIGH_RELEVANCE_INDUSTRIES,
    MEDIUM_RELEVANCE_INDUSTRIES,
    BLACKLISTED_COMPANIES,
    YC_BASE_SCORE,
)
from .nlp_scorer import score_company_relevance, score_job_description
from .web_enrichment import enrich_company


# ---------------------------------------------------------------------------
# Persistent company database
# ---------------------------------------------------------------------------
DB_PATH = os.path.join(os.path.dirname(__file__), "company_database.json")


def _load_db() -> dict:
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_db(db: dict):
    with open(DB_PATH, "w") as f:
        json.dump(db, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Individual signal scorers
# ---------------------------------------------------------------------------
def _score_curated_list(company_name: str) -> float:
    """Score based on membership in curated prestigious lists."""
    return CURATED_LOOKUP.get(company_name.lower(), 0.0)


def _score_from_bracket(value: Optional[int], brackets: list) -> float:
    """Generic bracket scorer — find the highest bracket the value fits."""
    if value is None:
        return 0.0
    for threshold, score in brackets:
        if value >= threshold:
            return score
    return 0.0


def _score_funding(enrichment: dict) -> float:
    """Score based on funding, employee count, and revenue."""
    scores = []

    total_funding = enrichment.get("total_funding")
    if total_funding:
        scores.append(_score_from_bracket(total_funding, FUNDING_SCORE_BRACKETS))

    employees = enrichment.get("employees")
    if employees:
        scores.append(_score_from_bracket(employees, EMPLOYEE_SCORE_BRACKETS))

    revenue = enrichment.get("revenue")
    if revenue:
        # Use funding brackets as proxy for revenue scoring
        scores.append(_score_from_bracket(revenue, FUNDING_SCORE_BRACKETS))

    # Funding stage bonus
    stage = enrichment.get("funding_stage", "")
    stage_scores = {
        "IPO": 95, "Series H": 90, "Series G": 88, "Series F": 85,
        "Series E": 80, "Series D": 75, "Series C": 65, "Series B": 55,
        "Series A": 40, "Seed": 25, "Pre-Seed": 15,
    }
    if stage in stage_scores:
        scores.append(stage_scores[stage])

    return max(scores) if scores else 0.0


def _score_industry_alignment(enrichment: dict, job_industries: list = None) -> float:
    """Score based on how aligned the company's industry is with AI/ML."""
    score = 0.0

    # From enrichment data
    industry = (enrichment.get("industry") or "").lower()
    if industry:
        for hi in HIGH_RELEVANCE_INDUSTRIES:
            if hi in industry:
                score = max(score, 90.0)
                break
        if score < 90:
            for mi in MEDIUM_RELEVANCE_INDUSTRIES:
                if mi in industry:
                    score = max(score, 60.0)
                    break

    # From job posting industries
    if job_industries:
        for ind in job_industries:
            ind_lower = ind.lower() if isinstance(ind, str) else ""
            for hi in HIGH_RELEVANCE_INDUSTRIES:
                if hi in ind_lower:
                    score = max(score, 85.0)
                    break
            for mi in MEDIUM_RELEVANCE_INDUSTRIES:
                if mi in ind_lower:
                    score = max(score, 55.0)
                    break

    return score


def _score_job_quality(jobs: list) -> float:
    """Aggregate job quality score from multiple job postings."""
    if not jobs:
        return 0.0

    scores = []
    for job in jobs:
        desc = job.get("description", "")
        if desc:
            result = score_job_description(desc)
            scores.append(result["overall"])

        # Salary direct signal
        salary_desc = job.get("formatted_salary_description", "")
        if salary_desc:
            salary_match = re.search(r"\$?([\d,]+)", salary_desc.replace(",", ""))
            if salary_match:
                try:
                    salary_val = int(salary_match.group(1))
                    if salary_val < 1000:
                        salary_val *= 1000  # convert k to full
                    scores.append(_score_from_bracket(salary_val, SALARY_SCORE_BRACKETS))
                except ValueError:
                    pass

        # Benefits signal
        benefits = job.get("benefits", [])
        if benefits:
            scores.append(min(100, len(benefits) * 15))

        # Application competition (fewer applies = potentially higher quality)
        applies = job.get("applies")
        views = job.get("views")
        if applies and views and views > 0:
            ratio = applies / views
            # Lower ratio = less competition = possibly more selective
            if ratio < 0.05:
                scores.append(70)
            elif ratio < 0.10:
                scores.append(50)
            elif ratio < 0.20:
                scores.append(30)

    return sum(scores) / len(scores) if scores else 0.0


# ---------------------------------------------------------------------------
# Main scoring & tiering
# ---------------------------------------------------------------------------
def compute_composite_score(
    company_name: str,
    enrichment: dict = None,
    jobs: list = None,
    yc_companies: set = None,
) -> dict:
    """
    Compute the composite score for a company from all available signals.

    Args:
        company_name: The company name
        enrichment: Pre-fetched enrichment data (or None to fetch)
        jobs: List of job dicts from the scraper for this company
        yc_companies: Set of YC company names (lowercase) if available

    Returns:
        dict with individual signal scores, composite score, and tier
    """
    # Check blacklist first
    if company_name.lower() in BLACKLISTED_COMPANIES:
        return {
            "company_name": company_name,
            "tier": "BLACKLISTED",
            "tier_label": "Blacklisted",
            "composite_score": 0,
            "signals": {},
            "scored_at": datetime.now().isoformat(),
        }

    # Gather enrichment if not provided
    if enrichment is None:
        enrichment = enrich_company(company_name)

    jobs = jobs or []

    # Build company description text for NLP
    desc_parts = []
    if enrichment.get("description"):
        desc_parts.append(enrichment["description"])
    for job in jobs[:5]:  # Use up to 5 job descriptions
        if job.get("company_description"):
            desc_parts.append(job["company_description"])
            break  # One company description is enough
    combined_desc = " ".join(desc_parts)

    # Compute individual signals
    curated = _score_curated_list(company_name)

    # YC bonus
    if yc_companies and company_name.lower() in yc_companies:
        curated = max(curated, YC_BASE_SCORE)

    funding = _score_funding(enrichment)

    nlp = score_company_relevance(
        combined_desc,
        enrichment.get("description", ""),
    )

    job_quality = _score_job_quality(jobs)

    job_industries = []
    for job in jobs:
        job_industries.extend(job.get("industries", []))
        job_industries.extend(job.get("formatted_industries", []))
    industry = _score_industry_alignment(enrichment, job_industries)

    # Weighted composite
    signals = {
        "curated_list": round(curated, 1),
        "funding_scale": round(funding, 1),
        "nlp_relevance": round(nlp, 1),
        "job_quality": round(job_quality, 1),
        "industry_alignment": round(industry, 1),
    }

    composite = 0.0
    for signal_name, weight in SCORING_WEIGHTS.items():
        composite += signals.get(signal_name, 0) * weight

    composite = round(min(100.0, composite), 1)

    # Determine tier
    tier = "T5_UNRANKED"
    for tier_name, threshold in sorted(
        TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True
    ):
        if composite >= threshold:
            tier = tier_name
            break

    return {
        "company_name": company_name,
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, "Unknown"),
        "composite_score": composite,
        "signals": signals,
        "enrichment_summary": {
            "industry": enrichment.get("industry"),
            "founded": enrichment.get("founded"),
            "employees": enrichment.get("employees"),
            "total_funding": enrichment.get("total_funding"),
            "funding_stage": enrichment.get("funding_stage"),
            "headquarters": enrichment.get("headquarters"),
        },
        "jobs_analyzed": len(jobs),
        "scored_at": datetime.now().isoformat(),
    }


def assign_tier(composite_score: float) -> str:
    """Quick tier assignment from a pre-computed composite score."""
    for tier_name, threshold in sorted(
        TIER_THRESHOLDS.items(), key=lambda x: x[1], reverse=True
    ):
        if composite_score >= threshold:
            return tier_name
    return "T5_UNRANKED"


# ---------------------------------------------------------------------------
# Batch ranking
# ---------------------------------------------------------------------------
def rank_companies(
    company_names: list[str],
    jobs_by_company: dict[str, list] = None,
    yc_companies: set = None,
    enrich: bool = True,
    save_to_db: bool = True,
) -> list[dict]:
    """
    Rank a batch of companies and return sorted results (highest first).

    Args:
        company_names: List of company names to rank
        jobs_by_company: {company_name: [job_dicts]} from scraper data
        yc_companies: Set of YC company names (for curated bonus)
        enrich: Whether to perform web enrichment (slower but more accurate)
        save_to_db: Whether to persist results to the company database

    Returns:
        List of score dicts sorted by composite_score descending
    """
    jobs_by_company = jobs_by_company or {}
    results = []
    total = len(company_names)
    db = _load_db() if save_to_db else {}

    for i, name in enumerate(company_names, 1):
        if i % 25 == 0:
            print(f"  Ranked {i}/{total} companies...")

        # Check if we have a recent score in DB
        db_key = name.lower()
        existing = db.get(db_key)
        if existing and not enrich:
            # Re-use cached score if not enriching
            results.append(existing)
            continue

        enrichment = None
        if enrich:
            try:
                enrichment = enrich_company(name)
            except Exception:
                enrichment = {}

        jobs = jobs_by_company.get(name, [])

        score_data = compute_composite_score(
            name,
            enrichment=enrichment,
            jobs=jobs,
            yc_companies=yc_companies,
        )

        results.append(score_data)

        if save_to_db:
            db[db_key] = score_data

    if save_to_db:
        _save_db(db)

    # Sort by composite score descending
    results.sort(key=lambda x: x.get("composite_score", 0), reverse=True)
    return results


def quick_score(company_name: str, jobs: list = None) -> dict:
    """
    Fast scoring without web enrichment — uses only curated lists,
    NLP on available job data, and job quality signals.
    Good for real-time annotation during scraping.
    """
    jobs = jobs or []

    # Curated list score
    curated = _score_curated_list(company_name)

    # NLP from job data (no web scraping)
    desc_parts = []
    for job in jobs[:3]:
        if job.get("company_description"):
            desc_parts.append(job["company_description"])
        if job.get("description"):
            desc_parts.append(job["description"][:500])
    combined = " ".join(desc_parts)
    nlp = score_company_relevance(combined) if combined else 0.0

    # Job quality
    jq = _score_job_quality(jobs)

    # Industry from job data
    job_industries = []
    for job in jobs:
        job_industries.extend(job.get("industries", []))
    industry = _score_industry_alignment({}, job_industries)

    # Simplified composite (no funding signal without enrichment)
    # Redistribute funding weight to other signals
    adjusted_weights = {
        "curated_list": 0.40,
        "nlp_relevance": 0.30,
        "job_quality": 0.18,
        "industry_alignment": 0.12,
    }

    signals = {
        "curated_list": round(curated, 1),
        "nlp_relevance": round(nlp, 1),
        "job_quality": round(jq, 1),
        "industry_alignment": round(industry, 1),
    }

    composite = sum(
        signals.get(k, 0) * w for k, w in adjusted_weights.items()
    )
    composite = round(min(100.0, composite), 1)

    tier = assign_tier(composite)

    return {
        "company_name": company_name,
        "tier": tier,
        "tier_label": TIER_LABELS.get(tier, "Unknown"),
        "composite_score": composite,
        "signals": signals,
        "mode": "quick",
        "scored_at": datetime.now().isoformat(),
    }


def get_company_tier(company_name: str) -> str:
    """
    Get the tier for a company from the database, or compute a quick score.
    Returns the tier string (e.g. 'T1_ELITE').
    """
    db = _load_db()
    db_key = company_name.lower()

    if db_key in db:
        return db[db_key].get("tier", "T5_UNRANKED")

    # Quick curated-list-only check (no web calls)
    curated = _score_curated_list(company_name)
    if curated >= 80:
        return "T1_ELITE"
    elif curated >= 60:
        return "T2_PREMIUM"
    elif curated >= 40:
        return "T3_STRONG"
    elif curated > 0:
        return "T4_STANDARD"

    return "T5_UNRANKED"


def get_tier_summary(ranked: list[dict]) -> dict:
    """Summarize the tier distribution of ranked companies."""
    summary = {tier: [] for tier in TIER_LABELS}
    for company in ranked:
        tier = company.get("tier", "T5_UNRANKED")
        if tier in summary:
            summary[tier].append(company["company_name"])

    return {
        tier: {
            "label": TIER_LABELS[tier],
            "count": len(companies),
            "companies": companies[:10],  # Top 10 per tier
        }
        for tier, companies in summary.items()
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    test_companies = sys.argv[1:] or [
        "OpenAI", "Anthropic", "Google", "Stripe", "Databricks",
        "Perplexity", "LangChain", "Actalent", "Unknown Corp",
    ]

    print(f"Ranking {len(test_companies)} companies...\n")
    ranked = rank_companies(test_companies, enrich=False, save_to_db=False)

    print(f"\n{'Company':<25} {'Tier':<15} {'Score':>6}  Signals")
    print("-" * 80)
    for r in ranked:
        sigs = r["signals"]
        sig_str = " | ".join(f"{k}:{v}" for k, v in sigs.items())
        print(f"{r['company_name']:<25} {r['tier_label']:<15} {r['composite_score']:>5.1f}  {sig_str}")

    print(f"\n--- Tier Summary ---")
    summary = get_tier_summary(ranked)
    for tier, info in summary.items():
        if info["count"] > 0:
            print(f"  {info['label']}: {info['count']} companies — {', '.join(info['companies'])}")
