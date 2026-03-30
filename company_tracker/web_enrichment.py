"""
Web Enrichment — scrape public sources to gather company metadata.

Sources:
  1. Wikipedia — summary, employee count, founding year, industry
  2. Crunchbase (public pages) — funding rounds, total raised, stage
  3. LinkedIn company pages (via existing session) — follower count, specialties

All scrapers use rate limiting and graceful fallbacks.
"""

import re
import time
import json
import os
import hashlib
from datetime import datetime, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Cache layer — avoid repeated scraping for the same company
# ---------------------------------------------------------------------------
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".enrichment_cache")
CACHE_TTL_DAYS = 7  # re-scrape after this many days


def _cache_path(company_name: str) -> str:
    slug = hashlib.md5(company_name.lower().encode()).hexdigest()
    return os.path.join(CACHE_DIR, f"{slug}.json")


def _read_cache(company_name: str) -> Optional[dict]:
    path = _cache_path(company_name)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            data = json.load(f)
        cached_at = datetime.fromisoformat(data.get("_cached_at", "2000-01-01"))
        if datetime.now() - cached_at > timedelta(days=CACHE_TTL_DAYS):
            return None  # stale
        return data
    except (json.JSONDecodeError, ValueError, KeyError):
        return None


def _write_cache(company_name: str, data: dict):
    os.makedirs(CACHE_DIR, exist_ok=True)
    data["_cached_at"] = datetime.now().isoformat()
    path = _cache_path(company_name)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


# ---------------------------------------------------------------------------
# Shared HTTP helpers
# ---------------------------------------------------------------------------
_SESSION = requests.Session()
_SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})

# Simple rate limiter: minimum seconds between requests per domain
_LAST_REQUEST: dict[str, float] = {}
_MIN_INTERVAL = 2.0  # seconds


def _rate_limited_get(url: str, **kwargs) -> Optional[requests.Response]:
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    now = time.time()
    last = _LAST_REQUEST.get(domain, 0)
    wait = _MIN_INTERVAL - (now - last)
    if wait > 0:
        time.sleep(wait)
    try:
        resp = _SESSION.get(url, timeout=15, **kwargs)
        _LAST_REQUEST[domain] = time.time()
        if resp.status_code == 200:
            return resp
    except requests.RequestException:
        pass
    return None


# ---------------------------------------------------------------------------
# 1. Wikipedia enrichment
# ---------------------------------------------------------------------------
def _parse_number(text: str) -> Optional[int]:
    """Parse numbers like '12,500', '~3.2 billion', '1.5M' from text."""
    if not text:
        return None
    text = text.strip().replace(",", "").replace("~", "").replace("+", "")

    multipliers = {
        "billion": 1_000_000_000, "b": 1_000_000_000,
        "million": 1_000_000, "m": 1_000_000,
        "thousand": 1_000, "k": 1_000,
    }

    text_lower = text.lower()
    for word, mult in multipliers.items():
        if word in text_lower:
            num_match = re.search(r"[\d.]+", text_lower)
            if num_match:
                try:
                    return int(float(num_match.group()) * mult)
                except ValueError:
                    pass

    # Plain number
    num_match = re.search(r"[\d]+", text)
    if num_match:
        try:
            return int(num_match.group())
        except ValueError:
            pass
    return None


def enrich_from_wikipedia(company_name: str) -> dict:
    """Fetch company metadata from Wikipedia's infobox and intro."""
    result = {
        "source": "wikipedia",
        "description": None,
        "industry": None,
        "founded": None,
        "employees": None,
        "revenue": None,
        "headquarters": None,
        "website": None,
    }

    # Use Wikipedia API for the summary
    search_url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{company_name} company",
        "srlimit": 3,
        "format": "json",
    }
    resp = _rate_limited_get(search_url, params=params)
    if not resp:
        return result

    data = resp.json()
    results = data.get("query", {}).get("search", [])
    if not results:
        return result

    # Pick the best matching page title
    page_title = results[0]["title"]

    # Fetch the page HTML for infobox parsing
    parse_params = {
        "action": "parse",
        "page": page_title,
        "prop": "text",
        "format": "json",
    }
    parse_resp = _rate_limited_get(search_url, params=parse_params)
    if not parse_resp:
        return result

    html = parse_resp.json().get("parse", {}).get("text", {}).get("*", "")
    soup = BeautifulSoup(html, "html.parser")

    # Extract infobox fields
    infobox = soup.find("table", class_="infobox")
    if infobox:
        rows = infobox.find_all("tr")
        for row in rows:
            header = row.find("th")
            value = row.find("td")
            if not header or not value:
                continue
            label = header.get_text(strip=True).lower()
            val_text = value.get_text(strip=True)

            if "industry" in label:
                result["industry"] = val_text
            elif "founded" in label:
                year_match = re.search(r"\b(19|20)\d{2}\b", val_text)
                if year_match:
                    result["founded"] = int(year_match.group())
            elif "employees" in label or "number of employees" in label:
                result["employees"] = _parse_number(val_text)
            elif "revenue" in label:
                result["revenue"] = _parse_number(val_text)
            elif "headquarters" in label or "hq" in label:
                result["headquarters"] = val_text
            elif "website" in label:
                link = value.find("a", href=True)
                if link:
                    result["website"] = link["href"]

    # Extract first paragraph as description
    paragraphs = soup.find_all("p")
    for p in paragraphs:
        text = p.get_text(strip=True)
        if len(text) > 50:  # skip stub paragraphs
            # Clean citation markers like [1], [2]
            text = re.sub(r"\[\d+\]", "", text).strip()
            result["description"] = text[:500]
            break

    return result


# ---------------------------------------------------------------------------
# 2. Crunchbase enrichment (public pages)
# ---------------------------------------------------------------------------
def enrich_from_crunchbase(company_name: str) -> dict:
    """Scrape public Crunchbase company page for funding data."""
    result = {
        "source": "crunchbase",
        "total_funding": None,
        "last_funding_round": None,
        "funding_stage": None,
        "investors": [],
        "founded": None,
        "employee_range": None,
    }

    # Crunchbase URL slug is typically lowercase with hyphens
    slug = company_name.lower().replace(" ", "-").replace(".", "-")
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    url = f"https://www.crunchbase.com/organization/{slug}"

    resp = _rate_limited_get(url)
    if not resp:
        return result

    soup = BeautifulSoup(resp.text, "html.parser")

    # Look for funding info in the page
    page_text = soup.get_text(" ", strip=True)

    # Total funding
    funding_match = re.search(
        r"Total Funding[:\s]*\$?([\d,.]+)\s*(B|M|K|billion|million|thousand)?",
        page_text, re.I
    )
    if funding_match:
        result["total_funding"] = _parse_number(
            funding_match.group(1) + (funding_match.group(2) or "")
        )

    # Funding stage
    for stage in ["IPO", "Series H", "Series G", "Series F", "Series E",
                  "Series D", "Series C", "Series B", "Series A", "Seed", "Pre-Seed"]:
        if stage.lower() in page_text.lower():
            result["funding_stage"] = stage
            break

    # Employee range
    emp_match = re.search(
        r"([\d,]+)\s*-\s*([\d,]+)\s*employees",
        page_text, re.I
    )
    if emp_match:
        result["employee_range"] = f"{emp_match.group(1)}-{emp_match.group(2)}"

    return result


# ---------------------------------------------------------------------------
# 3. DuckDuckGo instant answer (lightweight fallback)
# ---------------------------------------------------------------------------
def enrich_from_duckduckgo(company_name: str) -> dict:
    """Use DuckDuckGo instant answer API for a quick company summary."""
    result = {
        "source": "duckduckgo",
        "description": None,
        "website": None,
        "related_topics": [],
    }

    url = "https://api.duckduckgo.com/"
    params = {
        "q": f"{company_name} company",
        "format": "json",
        "no_redirect": 1,
        "skip_disambig": 1,
    }
    resp = _rate_limited_get(url, params=params)
    if not resp:
        return result

    data = resp.json()
    abstract = data.get("AbstractText", "")
    if abstract:
        result["description"] = abstract[:500]

    abstract_url = data.get("AbstractURL", "")
    if abstract_url:
        result["website"] = abstract_url

    # Related topics for additional context
    for topic in data.get("RelatedTopics", [])[:5]:
        if isinstance(topic, dict) and "Text" in topic:
            result["related_topics"].append(topic["Text"][:200])

    return result


# ---------------------------------------------------------------------------
# Main enrichment pipeline
# ---------------------------------------------------------------------------
def enrich_company(company_name: str, force_refresh: bool = False) -> dict:
    """
    Gather all available metadata for a company from web sources.
    Returns a merged dictionary with all signals.
    Uses caching to avoid repeated scraping.
    """
    if not force_refresh:
        cached = _read_cache(company_name)
        if cached:
            return cached

    merged = {
        "company_name": company_name,
        "enriched_at": datetime.now().isoformat(),
        "description": None,
        "industry": None,
        "founded": None,
        "employees": None,
        "employee_range": None,
        "revenue": None,
        "total_funding": None,
        "funding_stage": None,
        "investors": [],
        "headquarters": None,
        "website": None,
        "related_topics": [],
    }

    # 1. Wikipedia (most reliable for established companies)
    wiki_data = enrich_from_wikipedia(company_name)
    for key in ["description", "industry", "founded", "employees",
                "revenue", "headquarters", "website"]:
        if wiki_data.get(key) and not merged.get(key):
            merged[key] = wiki_data[key]

    # 2. Crunchbase (funding data)
    cb_data = enrich_from_crunchbase(company_name)
    for key in ["total_funding", "funding_stage", "investors",
                "employee_range", "founded"]:
        if cb_data.get(key) and not merged.get(key):
            merged[key] = cb_data[key]

    # 3. DuckDuckGo fallback (if we still have no description)
    if not merged["description"]:
        ddg_data = enrich_from_duckduckgo(company_name)
        if ddg_data.get("description"):
            merged["description"] = ddg_data["description"]
        if ddg_data.get("related_topics"):
            merged["related_topics"] = ddg_data["related_topics"]

    _write_cache(company_name, merged)
    return merged


def enrich_companies_batch(company_names: list[str],
                           max_concurrent: int = 1,
                           force_refresh: bool = False) -> dict[str, dict]:
    """
    Enrich multiple companies sequentially (respecting rate limits).
    Returns {company_name: enrichment_data}.
    """
    results = {}
    total = len(company_names)

    for i, name in enumerate(company_names, 1):
        print(f"  [{i}/{total}] Enriching {name}...")
        try:
            results[name] = enrich_company(name, force_refresh=force_refresh)
        except Exception as e:
            print(f"    Error enriching {name}: {e}")
            results[name] = {"company_name": name, "error": str(e)}

    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    test_companies = sys.argv[1:] or ["Anthropic", "Databricks", "Stripe"]
    print(f"Enriching {len(test_companies)} companies...\n")

    for company in test_companies:
        data = enrich_company(company, force_refresh=True)
        print(f"\n{'='*60}")
        print(f" {company}")
        print(f"{'='*60}")
        for k, v in data.items():
            if k.startswith("_") or not v:
                continue
            print(f"  {k}: {v}")
