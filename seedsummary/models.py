"""Core data structures shared across the pipeline."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Any, Optional


def slugify(value: str) -> str:
    """Stable, URL/ATS-friendly slug used as a company's primary key."""
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


@dataclass
class FundingEvent:
    """A single funding signal pulled from a source."""
    company_name: str
    stage: str = ""              # normalized, e.g. "seed", "series a"
    amount: str = ""             # raw text, e.g. "$12M"
    investors: list[str] = field(default_factory=list)
    source: str = ""             # source name, e.g. "TechCrunch — Venture"
    url: str = ""
    published: Optional[str] = None  # ISO date string
    blurb: str = ""              # description / article summary

    @property
    def published_date(self) -> Optional[date]:
        if not self.published:
            return None
        try:
            return datetime.fromisoformat(self.published).date()
        except ValueError:
            return None


@dataclass
class Job:
    """An open role pulled from a company's ATS."""
    title: str
    url: str = ""
    location: str = ""
    department: str = ""
    posted: Optional[str] = None     # ISO date string if known
    matched_role: str = ""           # which target role it matched, if any


@dataclass
class Company:
    """A funded company aggregated from one or more funding events, plus the
    hiring + scoring data we attach to it."""
    name: str
    slug: str = ""
    stage: str = ""
    amount: str = ""
    investors: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    blurb: str = ""
    funded_on: Optional[str] = None  # ISO date of most recent funding signal
    website: str = ""

    # Enrichment (filled later in the pipeline)
    domains: list[str] = field(default_factory=list)
    ai_signal: bool = False
    ats: dict[str, str] = field(default_factory=dict)  # {provider, token}
    jobs: list[Job] = field(default_factory=list)
    matched_jobs: list[Job] = field(default_factory=list)

    # Scoring
    score: float = 0.0
    score_breakdown: dict[str, float] = field(default_factory=dict)
    highlighted: bool = False
    suggest_watch: bool = False

    def __post_init__(self) -> None:
        if not self.slug:
            self.slug = slugify(self.name)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Company":
        jobs = [Job(**j) for j in d.get("jobs", [])]
        matched = [Job(**j) for j in d.get("matched_jobs", [])]
        d = {**d, "jobs": jobs, "matched_jobs": matched}
        # Drop unknown keys defensively so older data files still load.
        allowed = set(cls.__dataclass_fields__.keys())
        d = {k: v for k, v in d.items() if k in allowed}
        return cls(**d)
