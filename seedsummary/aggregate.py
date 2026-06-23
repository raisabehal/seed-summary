"""Merge raw FundingEvents (possibly several per company, from several sources)
into a de-duplicated list[Company], and apply VC portfolio attribution and the
stage filter from the profile."""
from __future__ import annotations

from typing import Any

from .models import Company, FundingEvent, slugify


def _pick_better(a: str, b: str) -> str:
    """Prefer the longer/non-empty of two strings (e.g. richer blurb/amount)."""
    return a if len(a or "") >= len(b or "") else b


def merge_events(events: list[FundingEvent]) -> list[Company]:
    by_slug: dict[str, Company] = {}
    for ev in events:
        slug = slugify(ev.company_name)
        if not slug:
            continue
        c = by_slug.get(slug)
        if c is None:
            c = Company(name=ev.company_name, slug=slug)
            by_slug[slug] = c
        c.stage = c.stage or ev.stage
        c.amount = _pick_better(c.amount, ev.amount)
        c.blurb = _pick_better(c.blurb, ev.blurb)
        for inv in ev.investors:
            if inv not in c.investors:
                c.investors.append(inv)
        if ev.source and ev.source not in c.sources:
            c.sources.append(ev.source)
        if ev.url and ev.url not in c.urls:
            c.urls.append(ev.url)
        # Keep the most recent funding date.
        if ev.published and (c.funded_on is None or ev.published > c.funded_on):
            c.funded_on = ev.published
    return list(by_slug.values())


def apply_vc_attribution(companies: list[Company], attribution: dict[str, set[str]]) -> None:
    for c in companies:
        investors = attribution.get(c.slug)
        if investors:
            for inv in investors:
                if inv not in c.investors:
                    c.investors.append(inv)


def filter_by_stage(companies: list[Company], profile: dict[str, Any]) -> list[Company]:
    target = {s.lower() for s in profile.get("target_stages", [])}
    if not target:
        return companies
    # Keep companies whose stage is in target, OR whose stage is unknown
    # (better to surface and let scoring rank it than to silently drop).
    return [c for c in companies if (not c.stage) or c.stage.lower() in target]
