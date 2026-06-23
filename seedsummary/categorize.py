"""Domain categorization, AI-signal detection, and matching open jobs to your
target roles. Operates purely on a company's text + jobs against profile.yml."""
from __future__ import annotations

from typing import Any

from .models import Company, Job


def _company_text(c: Company) -> str:
    parts = [c.name, c.blurb, " ".join(c.investors)]
    return " ".join(parts).lower()


def categorize_domains(company: Company, profile: dict[str, Any]) -> list[str]:
    text = _company_text(company)
    hits = []
    for dom in profile.get("target_domains", []):
        if any(kw.lower() in text for kw in dom.get("match", [])):
            hits.append(dom["name"])
    return hits


def detect_ai_signal(company: Company, profile: dict[str, Any]) -> bool:
    text = _company_text(company) + " " + " ".join(j.title.lower() for j in company.jobs)
    keywords = (profile.get("ai_signal") or {}).get("match", [])
    return any(kw.lower() in text for kw in keywords)


def match_jobs_to_roles(jobs: list[Job], profile: dict[str, Any]) -> list[Job]:
    """Return the subset of jobs that match a target role, tagging each with the
    role it matched. A job matches the first role whose keywords appear in its
    title."""
    matched: list[Job] = []
    roles = profile.get("target_roles", [])
    for job in jobs:
        title = (job.title or "").lower()
        for role in roles:
            if any(kw.lower() in title for kw in role.get("match", [])):
                job.matched_role = role["name"]
                matched.append(job)
                break
    return matched


def enrich(company: Company, profile: dict[str, Any]) -> None:
    """Fill domains, ai_signal, and matched_jobs on the company in place."""
    company.domains = categorize_domains(company, profile)
    company.ai_signal = detect_ai_signal(company, profile)
    company.matched_jobs = match_jobs_to_roles(company.jobs, profile)
