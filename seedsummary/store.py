"""Persistence of weekly results to data/ as JSON, plus week-over-week diffing
so we can flag NEW roles at watched companies."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Optional

from .models import Company, Job


def run_filename(d: date | None = None) -> str:
    d = d or date.today()
    return f"run-{d.isoformat()}.json"


def save_run(data_dir: Path, companies: list[Company], when: date | None = None) -> Path:
    when = when or date.today()
    payload = {
        "generated_at": when.isoformat(),
        "company_count": len(companies),
        "companies": [c.to_dict() for c in companies],
    }
    path = data_dir / run_filename(when)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # Also write/refresh a stable pointer to the latest run.
    (data_dir / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_latest(data_dir: Path) -> Optional[dict]:
    p = data_dir / "latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def load_previous_run(data_dir: Path, exclude: str) -> Optional[dict]:
    """Load the most recent run file that isn't `exclude` (the current run)."""
    runs = sorted(data_dir.glob("run-*.json"))
    runs = [r for r in runs if r.name != exclude]
    if not runs:
        return None
    try:
        return json.loads(runs[-1].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def new_jobs_since(prev_run: Optional[dict], company: Company) -> list[Job]:
    """Jobs present this week that weren't in the previous run for the same
    company (matched by job URL, falling back to title)."""
    if not prev_run:
        return list(company.jobs)
    prev_company = next(
        (c for c in prev_run.get("companies", []) if c.get("slug") == company.slug),
        None,
    )
    if not prev_company:
        return list(company.jobs)
    prev_keys = {
        (j.get("url") or j.get("title")) for j in prev_company.get("jobs", [])
    }
    return [j for j in company.jobs if (j.url or j.title) not in prev_keys]
