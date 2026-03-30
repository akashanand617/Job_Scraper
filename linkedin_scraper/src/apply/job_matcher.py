"""
Job match scoring engine for the Auto-Apply module.
Scores jobs against a user profile's preferences (target roles, skills, location, salary, etc.).
Complements the ATS match_scorer which scores resume-to-job text overlap.
"""

import re
from typing import List, Optional

from .models import UserProfile, ScoredJob, JobScoreBreakdown

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


class JobMatcher:
    """Scores scraped jobs against a user profile's preferences."""

    def __init__(self, profile: UserProfile):
        self.profile = profile
        self.skills_lower = {s.lower() for s in profile.skills}

    def score_job(self, job: dict) -> ScoredJob:
        """Score a single job against the user profile. Returns 0-100."""
        skills = self._score_skills(job)
        title = self._score_title(job)
        exp_level = self._score_experience_level(job)
        location = self._score_location(job)
        salary = self._score_salary(job)
        company = self._score_company(job)

        overall = skills + title + exp_level + location + salary + company

        return ScoredJob(
            job_id=str(job.get("job_id", "")),
            title=job.get("title", "Unknown"),
            company_name=job.get("company_name", "Unknown"),
            overall_score=round(overall, 1),
            breakdown=JobScoreBreakdown(
                skills_score=round(skills, 1),
                title_score=round(title, 1),
                experience_level_score=round(exp_level, 1),
                location_score=round(location, 1),
                salary_score=round(salary, 1),
                company_score=round(company, 1),
            ),
            url=job.get("url"),
            location=job.get("formatted_location"),
            experience_level=job.get("experience_level"),
            workplace_type=job.get("workplace_type_label"),
            salary=job.get("formatted_salary_description"),
            posted_dt=job.get("posted_dt"),
        )

    def score_all(self, jobs: List[dict], min_score: float = 0.0, top_n: Optional[int] = None) -> List[ScoredJob]:
        """Score all jobs, filter by min_score, sort descending, optionally limit."""
        results = []
        for job in jobs:
            # Skip blacklisted companies
            company = (job.get("company_name") or "").lower()
            if any(bl.lower() in company for bl in self.profile.blacklist_companies):
                continue

            try:
                scored = self.score_job(job)
                if scored.overall_score >= min_score:
                    results.append(scored)
            except Exception:
                continue

        results.sort(key=lambda x: x.overall_score, reverse=True)
        if top_n:
            results = results[:top_n]
        return results

    # -----------------------------------------------------------------------
    # Component Scorers (0-max_points each)
    # -----------------------------------------------------------------------

    def _score_skills(self, job: dict) -> float:
        """Skills match: 0-40 points."""
        if not self.skills_lower:
            return 20.0  # Neutral if user has no skills listed

        # Combine job skills from multiple fields
        job_text = " ".join(filter(None, [
            job.get("skills_description", ""),
            job.get("description", ""),
        ])).lower()

        if not job_text:
            return 20.0

        if RAPIDFUZZ_AVAILABLE:
            # Use fuzzy matching for better recall
            matched = 0
            for skill in self.skills_lower:
                # Check exact substring match first
                if skill in job_text:
                    matched += 1
                else:
                    # Fuzzy match against job text words
                    words = re.findall(r'\b\w{3,}\b', job_text)
                    best = process.extractOne(skill, words, scorer=fuzz.ratio)
                    if best and best[1] >= 80:
                        matched += 1

            ratio = matched / len(self.skills_lower) if self.skills_lower else 0
        else:
            # Simple substring matching fallback
            matched = sum(1 for s in self.skills_lower if s in job_text)
            ratio = matched / len(self.skills_lower) if self.skills_lower else 0

        return min(40.0, ratio * 40.0)

    def _score_title(self, job: dict) -> float:
        """Title match: 0-20 points."""
        if not self.profile.target_roles:
            return 10.0  # Neutral

        job_title = (job.get("title") or "").lower()
        if not job_title:
            return 0.0

        best_score = 0.0
        for role in self.profile.target_roles:
            role_lower = role.lower()

            # Exact substring match
            if role_lower in job_title or job_title in role_lower:
                best_score = max(best_score, 1.0)
                continue

            if RAPIDFUZZ_AVAILABLE:
                ratio = fuzz.token_sort_ratio(role_lower, job_title) / 100.0
                best_score = max(best_score, ratio)
            else:
                # Simple word overlap
                role_words = set(role_lower.split())
                title_words = set(job_title.split())
                if role_words and title_words:
                    overlap = len(role_words & title_words) / len(role_words)
                    best_score = max(best_score, overlap)

        return min(20.0, best_score * 20.0)

    def _score_experience_level(self, job: dict) -> float:
        """Experience level match: 0-15 points."""
        if not self.profile.preferred_experience_levels:
            return 7.5  # Neutral

        job_level = (job.get("experience_level") or "").lower()
        if not job_level:
            return 7.5

        if job_level in [l.lower() for l in self.profile.preferred_experience_levels]:
            return 15.0

        # Adjacent levels get partial credit
        level_order = ["intern", "entry", "associate", "mid-senior", "director", "executive"]
        try:
            job_idx = level_order.index(job_level)
            pref_indices = [level_order.index(l.lower()) for l in self.profile.preferred_experience_levels
                          if l.lower() in level_order]
            if pref_indices:
                min_distance = min(abs(job_idx - pi) for pi in pref_indices)
                if min_distance == 1:
                    return 10.0
                elif min_distance == 2:
                    return 5.0
        except ValueError:
            pass

        return 0.0

    def _score_location(self, job: dict) -> float:
        """Location/workplace match: 0-10 points."""
        score = 0.0

        # Workplace type match (0-6 points)
        if self.profile.preferred_workplace:
            job_wp = (job.get("workplace_type_label") or "").lower()
            if job_wp and job_wp in [w.lower() for w in self.profile.preferred_workplace]:
                score += 6.0
            elif not job_wp:
                score += 3.0  # Unknown, neutral
        else:
            score += 3.0  # No preference, neutral

        # Location match (0-4 points)
        if self.profile.preferred_locations:
            job_loc = (job.get("formatted_location") or "").lower()
            if job_loc:
                for pref_loc in self.profile.preferred_locations:
                    if pref_loc.lower() in job_loc or job_loc in pref_loc.lower():
                        score += 4.0
                        break
            else:
                score += 2.0  # Unknown location, neutral
        else:
            score += 2.0  # No preference

        return min(10.0, score)

    def _score_salary(self, job: dict) -> float:
        """Salary match: 0-10 points."""
        if not self.profile.min_salary:
            return 5.0  # No preference, neutral

        salary_text = job.get("formatted_salary_description") or ""
        if not salary_text:
            return 5.0  # No salary info, neutral

        # Extract salary numbers from text
        numbers = re.findall(r'[\$]?\s*([\d,]+(?:\.\d+)?)\s*(?:K|k)?', salary_text)
        if not numbers:
            return 5.0

        parsed_salaries = []
        for num_str in numbers:
            try:
                num = float(num_str.replace(",", ""))
                # Handle "K" notation
                if num < 1000 and ("k" in salary_text.lower() or "K" in salary_text):
                    num *= 1000
                # Handle hourly rates (rough annual conversion)
                if "hour" in salary_text.lower() and num < 500:
                    num *= 2080
                parsed_salaries.append(num)
            except ValueError:
                continue

        if not parsed_salaries:
            return 5.0

        max_salary = max(parsed_salaries)
        if max_salary >= self.profile.min_salary:
            return 10.0
        elif max_salary >= self.profile.min_salary * 0.9:
            return 7.0
        elif max_salary >= self.profile.min_salary * 0.8:
            return 4.0
        return 1.0

    def _score_company(self, job: dict) -> float:
        """Company preference: 0-5 points."""
        if not self.profile.target_companies:
            return 2.5  # Neutral

        company = (job.get("company_name") or "").lower()
        if not company:
            return 2.5

        for target in self.profile.target_companies:
            if target.lower() in company or company in target.lower():
                return 5.0

        return 2.5  # Not in target list but not blacklisted
