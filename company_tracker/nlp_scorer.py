"""
NLP Scorer — use transformer models for semantic analysis of companies.

Two modes:
  1. Full mode (sentence-transformers available): uses real embeddings for
     semantic similarity between company descriptions and target profiles.
  2. Fallback mode: keyword-frequency TF-IDF-style scoring when transformers
     are not installed (e.g., in Lambda or lightweight environments).

The scorer produces a 0-100 relevance score per company.
"""

import re
import math
from typing import Optional
from collections import Counter

from .tier_config import TARGET_PROFILES, PROFILE_WEIGHTS, HIGH_VALUE_KEYWORDS


# ---------------------------------------------------------------------------
# Try to load sentence-transformers; fall back gracefully
# ---------------------------------------------------------------------------
_TRANSFORMER_AVAILABLE = False
_MODEL = None
_PROFILE_EMBEDDINGS = None

def _load_transformer_model():
    """Lazy-load the transformer model on first use."""
    global _TRANSFORMER_AVAILABLE, _MODEL, _PROFILE_EMBEDDINGS
    if _MODEL is not None:
        return

    try:
        from sentence_transformers import SentenceTransformer
        # all-MiniLM-L6-v2: fast, good quality, 384-dim embeddings
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
        _TRANSFORMER_AVAILABLE = True

        # Pre-encode target profiles
        _PROFILE_EMBEDDINGS = {}
        for key, text in TARGET_PROFILES.items():
            _PROFILE_EMBEDDINGS[key] = _MODEL.encode(text, normalize_embeddings=True)

        print("NLP Scorer: transformer model loaded (all-MiniLM-L6-v2)")
    except ImportError:
        _TRANSFORMER_AVAILABLE = False
        print("NLP Scorer: sentence-transformers not installed, using keyword fallback")
    except Exception as e:
        _TRANSFORMER_AVAILABLE = False
        print(f"NLP Scorer: transformer load failed ({e}), using keyword fallback")


# ---------------------------------------------------------------------------
# Transformer-based scoring
# ---------------------------------------------------------------------------
def _cosine_similarity(a, b) -> float:
    """Compute cosine similarity between two numpy vectors."""
    import numpy as np
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def _score_with_transformer(text: str) -> float:
    """
    Compute weighted semantic similarity of text against all target profiles.
    Returns 0-100 score.
    """
    if not text or not _MODEL:
        return 0.0

    # Encode the input text
    text_embedding = _MODEL.encode(text, normalize_embeddings=True)

    # Compute weighted similarity across all profiles
    weighted_score = 0.0
    for profile_key, profile_emb in _PROFILE_EMBEDDINGS.items():
        sim = _cosine_similarity(text_embedding, profile_emb)
        # Map cosine similarity (-1 to 1) to (0 to 100)
        # In practice, most similarities are 0.0 to 0.8
        normalized = max(0.0, sim) * 100  # clamp negatives to 0
        weight = PROFILE_WEIGHTS.get(profile_key, 0.0)
        weighted_score += normalized * weight

    return min(100.0, weighted_score)


# ---------------------------------------------------------------------------
# Keyword fallback scoring (TF-IDF-inspired)
# ---------------------------------------------------------------------------

# Build a comprehensive keyword vocabulary with weights
_KEYWORD_SCORES = {}
for kw in HIGH_VALUE_KEYWORDS:
    _KEYWORD_SCORES[kw.lower()] = 3.0  # High-value keywords

# Additional domain keywords with lower weights
_DOMAIN_KEYWORDS = {
    "artificial intelligence": 2.5, "neural network": 2.5,
    "natural language processing": 2.5, "generative ai": 2.5,
    "gpu": 2.0, "cuda": 2.0, "tensor": 2.0, "pytorch": 2.0,
    "tensorflow": 2.0, "jax": 2.0,
    "cloud": 1.5, "aws": 1.5, "gcp": 1.5, "azure": 1.5,
    "kubernetes": 1.5, "docker": 1.5, "microservices": 1.5,
    "startup": 1.5, "venture": 1.5, "unicorn": 2.0,
    "innovation": 1.0, "cutting-edge": 1.0, "state-of-the-art": 1.5,
    "peer-reviewed": 2.0, "neurips": 2.5, "icml": 2.5, "iclr": 2.5,
    "acl": 2.0, "cvpr": 2.0, "aaai": 2.0,
    "safety": 1.5, "alignment": 2.0, "responsible ai": 1.5,
    "autonomous": 2.0, "robotics": 2.0, "self-driving": 2.0,
    "quantitative": 1.5, "algorithmic trading": 2.0,
    "open source": 1.5, "api": 1.0, "platform": 1.0,
    "scale": 1.0, "billion": 1.5, "million": 1.0,
    "funded": 1.5, "raised": 1.5, "valuation": 1.5,
    "ipo": 2.0, "acquisition": 1.0,
}
_KEYWORD_SCORES.update(_DOMAIN_KEYWORDS)

# Negative signals
_NEGATIVE_KEYWORDS = {
    "staffing": -3.0, "recruiting agency": -3.0, "temp agency": -3.0,
    "outsourcing": -2.0, "body shop": -3.0, "headhunter": -2.0,
    "job board": -3.0, "job aggregator": -3.0,
    "entry-level only": -1.0, "no benefits": -2.0,
}
_KEYWORD_SCORES.update(_NEGATIVE_KEYWORDS)


def _score_with_keywords(text: str) -> float:
    """
    Keyword-frequency scoring as a fallback when transformers aren't available.
    Returns 0-100 score.
    """
    if not text:
        return 0.0

    text_lower = text.lower()
    total_score = 0.0
    matches = 0

    for keyword, weight in _KEYWORD_SCORES.items():
        count = text_lower.count(keyword)
        if count > 0:
            # Diminishing returns for repeated keywords
            contribution = weight * math.log(1 + count)
            total_score += contribution
            matches += 1

    if matches == 0:
        return 0.0

    # Normalize: scale based on keyword density
    # Max practical raw score is ~50-80 for highly relevant text
    # Map to 0-100 range with sigmoid-like scaling
    normalized = 100 * (1 - math.exp(-total_score / 15))
    return max(0.0, min(100.0, normalized))


# ---------------------------------------------------------------------------
# Job description quality analysis
# ---------------------------------------------------------------------------
def score_job_description(description: str) -> dict:
    """
    Analyze a job description for quality signals.
    Returns a dict with sub-scores and an overall job quality score (0-100).
    """
    if not description:
        return {"overall": 0, "signals": {}}

    text_lower = description.lower()
    signals = {}

    # Technical depth score
    tech_keywords = [
        "machine learning", "deep learning", "neural network", "transformer",
        "LLM", "NLP", "computer vision", "reinforcement learning",
        "distributed systems", "large scale", "pytorch", "tensorflow",
        "research", "publication", "PhD",
    ]
    tech_hits = sum(1 for kw in tech_keywords if kw.lower() in text_lower)
    signals["technical_depth"] = min(100, tech_hits * 15)

    # Compensation signals
    comp_keywords = ["equity", "stock", "RSU", "bonus", "competitive salary",
                     "401k", "health insurance", "dental", "vision"]
    comp_hits = sum(1 for kw in comp_keywords if kw.lower() in text_lower)
    signals["compensation_quality"] = min(100, comp_hits * 20)

    # Growth / culture signals
    growth_keywords = ["fast-growing", "series", "funded", "unicorn", "IPO",
                       "learning", "mentorship", "career growth", "promotion",
                       "remote", "flexible", "unlimited PTO"]
    growth_hits = sum(1 for kw in growth_keywords if kw.lower() in text_lower)
    signals["growth_culture"] = min(100, growth_hits * 15)

    # Seniority / impact signals
    impact_keywords = ["lead", "architect", "design", "own", "drive",
                       "strategic", "cross-functional", "stakeholder",
                       "org-wide", "company-wide"]
    impact_hits = sum(1 for kw in impact_keywords if kw.lower() in text_lower)
    signals["impact_level"] = min(100, impact_hits * 15)

    # Salary extraction
    salary_match = re.search(
        r"\$\s*([\d,]+)\s*(?:k|K)?\s*(?:-|to)\s*\$?\s*([\d,]+)\s*(?:k|K)?",
        description
    )
    if salary_match:
        try:
            low = int(salary_match.group(1).replace(",", ""))
            high = int(salary_match.group(2).replace(",", ""))
            # Normalize if in thousands
            if low < 1000:
                low *= 1000
            if high < 1000:
                high *= 1000
            midpoint = (low + high) / 2
            # Score based on midpoint salary
            if midpoint >= 300000:
                signals["salary_score"] = 100
            elif midpoint >= 200000:
                signals["salary_score"] = 80
            elif midpoint >= 150000:
                signals["salary_score"] = 60
            elif midpoint >= 100000:
                signals["salary_score"] = 40
            else:
                signals["salary_score"] = 20
        except (ValueError, IndexError):
            pass

    # Weighted overall score
    weights = {
        "technical_depth": 0.35,
        "compensation_quality": 0.20,
        "growth_culture": 0.15,
        "impact_level": 0.15,
        "salary_score": 0.15,
    }
    overall = 0.0
    total_weight = 0.0
    for signal_name, weight in weights.items():
        if signal_name in signals:
            overall += signals[signal_name] * weight
            total_weight += weight

    if total_weight > 0:
        overall = overall / total_weight  # Normalize if some signals missing

    return {"overall": round(overall, 1), "signals": signals}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def score_company_relevance(description: str,
                            company_description: str = None) -> float:
    """
    Score how relevant a company is based on its description text.
    Combines company description + any additional context.
    Returns 0-100.
    """
    # Merge available text
    texts = []
    if description:
        texts.append(description)
    if company_description:
        texts.append(company_description)

    if not texts:
        return 0.0

    combined = " ".join(texts)

    # Try transformer first, fall back to keywords
    _load_transformer_model()
    if _TRANSFORMER_AVAILABLE:
        return round(_score_with_transformer(combined), 1)
    else:
        return round(_score_with_keywords(combined), 1)


def score_company_batch(companies: list[dict]) -> list[dict]:
    """
    Score a batch of companies.
    Each company dict should have at minimum 'company_name' and optionally
    'description', 'company_description'.

    Returns the same list with 'nlp_score' and 'job_quality_score' added.
    """
    _load_transformer_model()

    for company in companies:
        desc = company.get("description", "") or ""
        co_desc = company.get("company_description", "") or ""

        company["nlp_score"] = score_company_relevance(desc, co_desc)

        # If job descriptions are available, score them too
        job_descs = company.get("job_descriptions", [])
        if job_descs:
            jq_scores = [score_job_description(jd)["overall"] for jd in job_descs]
            company["job_quality_score"] = round(
                sum(jq_scores) / len(jq_scores), 1
            ) if jq_scores else 0
        else:
            company["job_quality_score"] = 0

    return companies


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Quick test
    test_texts = [
        "OpenAI is an artificial intelligence research laboratory building safe AGI. "
        "We publish at NeurIPS, ICML, and develop large language models like GPT.",

        "A staffing agency that connects candidates with temporary positions in "
        "various industries. We are a job board and recruiting service.",

        "An innovative fintech startup using machine learning for fraud detection. "
        "Series B funded, 200 employees, competitive equity packages.",
    ]

    for text in test_texts:
        score = score_company_relevance(text)
        quality = score_job_description(text)
        print(f"\nText: {text[:80]}...")
        print(f"  Relevance score: {score}")
        print(f"  Job quality: {quality}")
