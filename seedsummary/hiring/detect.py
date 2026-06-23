"""Detect which ATS a company uses by probing candidate board tokens.

Most funded startups host jobs on Greenhouse/Lever/Ashby/Workable under a board
token that is some normalization of their name. We generate a few candidate
tokens and probe each provider until one returns jobs. Results are cached on
the company (company.ats) so the watchlist can re-fetch cheaply next week.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ..models import Company, Job
from .ats import PROVIDERS, fetch_jobs

log = logging.getLogger("seedsummary.hiring.detect")


def candidate_tokens(name: str, website: str = "") -> list[str]:
    base = name.lower().strip()
    # Drop common corporate suffixes/words.
    base = re.sub(r"\b(inc|llc|ltd|corp|co|the|ai|labs|technologies|tech|health|io)\b", " ", base)
    alnum = re.sub(r"[^a-z0-9]+", "", base)         # acmehealth
    hyphen = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")  # acme-health
    first = (re.split(r"[^a-z0-9]+", name.lower()) or [""])[0]

    candidates = [alnum, hyphen, first]
    if website:
        host = re.sub(r"^https?://(www\.)?", "", website).split("/")[0]
        domain = host.split(".")[0]
        candidates.append(re.sub(r"[^a-z0-9]+", "", domain.lower()))

    # De-dupe, drop empties and very short tokens.
    seen, out = set(), []
    for c in candidates:
        if c and len(c) >= 3 and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def detect_and_fetch(company: Company, http, max_probes: int = 6) -> list[Job]:
    """Find the company's ATS and return its open jobs. Caches provider/token
    on company.ats. If company.ats is already set, just refetch it."""
    if company.ats.get("provider") and company.ats.get("token"):
        return fetch_jobs(company.ats["provider"], company.ats["token"], http)

    tokens = candidate_tokens(company.name, company.website)
    probes = 0
    for provider in PROVIDERS:
        for token in tokens:
            if probes >= max_probes:
                return []
            probes += 1
            jobs = fetch_jobs(provider, token, http)
            if jobs:
                company.ats = {"provider": provider, "token": token}
                log.info("ATS hit: %s -> %s/%s (%d jobs)", company.name, provider, token, len(jobs))
                return jobs
    return []
