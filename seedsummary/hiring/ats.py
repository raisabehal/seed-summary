"""Clients for the public, free job-board APIs of the major ATS providers.

Each client takes a board "token" (the company's slug on that ATS) and returns
a normalized list[Job]. All return [] on any failure.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..models import Job

log = logging.getLogger("seedsummary.hiring.ats")


def _iso_from_ms(ms: Any) -> Optional[str]:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None


def _iso_from_str(s: Any) -> Optional[str]:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return None


def greenhouse(token: str, http) -> list[Job]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false"
    data = http.get_json(url)
    if not data or "jobs" not in data:
        return []
    jobs = []
    for j in data["jobs"]:
        loc = (j.get("location") or {}).get("name", "")
        depts = ", ".join(d.get("name", "") for d in (j.get("departments") or []))
        jobs.append(Job(
            title=j.get("title", ""),
            url=j.get("absolute_url", ""),
            location=loc,
            department=depts,
            posted=_iso_from_str(j.get("updated_at")),
        ))
    return jobs


def lever(token: str, http) -> list[Job]:
    url = f"https://api.lever.co/v0/postings/{token}?mode=json"
    data = http.get_json(url)
    if not isinstance(data, list):
        return []
    jobs = []
    for j in data:
        cats = j.get("categories") or {}
        jobs.append(Job(
            title=j.get("text", ""),
            url=j.get("hostedUrl", "") or j.get("applyUrl", ""),
            location=cats.get("location", ""),
            department=cats.get("team", ""),
            posted=_iso_from_ms(j.get("createdAt")),
        ))
    return jobs


def ashby(token: str, http) -> list[Job]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{token}?includeCompensation=false"
    data = http.get_json(url)
    if not data or "jobs" not in data:
        return []
    jobs = []
    for j in data["jobs"]:
        jobs.append(Job(
            title=j.get("title", ""),
            url=j.get("jobUrl", "") or j.get("applyUrl", ""),
            location=j.get("location", "") or j.get("locationName", ""),
            department=j.get("department", "") or j.get("team", ""),
            posted=_iso_from_str(j.get("publishedAt")),
        ))
    return jobs


def workable(token: str, http) -> list[Job]:
    url = f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true"
    data = http.get_json(url)
    if not data or "jobs" not in data:
        return []
    jobs = []
    for j in data["jobs"]:
        loc_parts = [j.get("city", ""), j.get("country", "")]
        jobs.append(Job(
            title=j.get("title", ""),
            url=j.get("url", "") or j.get("shortlink", ""),
            location=", ".join(p for p in loc_parts if p),
            department=j.get("department", ""),
            posted=_iso_from_str(j.get("published") or j.get("created_at")),
        ))
    return jobs


# Provider name -> client function. Order = probe priority.
PROVIDERS = {
    "greenhouse": greenhouse,
    "lever": lever,
    "ashby": ashby,
    "workable": workable,
}


def fetch_jobs(provider: str, token: str, http) -> list[Job]:
    fn = PROVIDERS.get(provider)
    if not fn:
        return []
    try:
        return fn(token, http)
    except Exception as exc:  # noqa: BLE001
        log.warning("ATS fetch failed (%s/%s): %s", provider, token, exc)
        return []
