"""Priority scoring. Each component is computed in 0..1, multiplied by its
weight from profile.yml, summed, then normalized to 0..100 across the batch so
the weekly email always has a clean ranking."""
from __future__ import annotations

from datetime import date
from typing import Any

from .models import Company


def _recency_component(funded_on: str | None, lookback_days: int) -> float:
    if not funded_on:
        return 0.3  # unknown date — mild, non-zero credit
    try:
        d = date.fromisoformat(funded_on)
    except ValueError:
        return 0.3
    age = (date.today() - d).days
    if age <= 0:
        return 1.0
    if age >= lookback_days:
        return 0.1
    return max(0.1, 1.0 - age / lookback_days)


def _seniority_factor(company: Company, profile: dict[str, Any]) -> float:
    kws = [k.lower() for k in profile.get("seniority_bonus_keywords", [])]
    if not company.matched_jobs or not kws:
        return 1.0
    senior = sum(1 for j in company.matched_jobs if any(k in j.title.lower() for k in kws))
    frac = senior / len(company.matched_jobs)
    return 1.0 + 0.15 * frac  # up to +15%


def raw_score(company: Company, profile: dict[str, Any]) -> dict[str, float]:
    weights = profile.get("weights", {})
    lookback = int(profile.get("funding_lookback_days", 30))

    # role_match: any matched jobs? scaled by seniority.
    role = 1.0 if company.matched_jobs else 0.0
    role *= _seniority_factor(company, profile)

    # domain_match: weighted by each matched domain's weight.
    dom_defs = {d["name"]: float(d.get("weight", 1.0)) for d in profile.get("target_domains", [])}
    domain = min(1.0, sum(dom_defs.get(d, 0.0) for d in company.domains))

    ai = 1.0 if company.ai_signal else 0.0

    recency = _recency_component(company.funded_on, lookback)

    # hiring_volume: saturating at 5 relevant roles.
    vol = min(1.0, len(company.matched_jobs) / 5.0)

    breakdown = {
        "role_match": role * float(weights.get("role_match", 0)),
        "domain_match": domain * float(weights.get("domain_match", 0)),
        "ai_signal": ai * float(weights.get("ai_signal", 0)),
        "funding_recency": recency * float(weights.get("funding_recency", 0)),
        "hiring_volume": vol * float(weights.get("hiring_volume", 0)),
    }

    # stage_fit multiplies the whole thing.
    stage_weights = profile.get("stage_weights", {})
    stage_mult = float(stage_weights.get(company.stage, 1.0)) if company.stage else 0.9
    stage_w = float(weights.get("stage_fit", 0))
    # Blend: stage acts as a multiplier on the subtotal, gated by stage_fit weight.
    subtotal = sum(breakdown.values())
    blended_mult = 1.0 + stage_w * (stage_mult - 1.0)
    breakdown["_subtotal"] = subtotal
    breakdown["_stage_mult"] = blended_mult
    breakdown["_raw"] = subtotal * blended_mult
    return breakdown


def score_batch(companies: list[Company], profile: dict[str, Any]) -> None:
    """Compute raw scores, then normalize to 0..100 across the batch. Mutates
    companies in place (sets .score, .score_breakdown, .highlighted,
    .suggest_watch)."""
    if not companies:
        return
    for c in companies:
        c.score_breakdown = raw_score(c, profile)

    max_raw = max((c.score_breakdown["_raw"] for c in companies), default=0.0) or 1.0
    threshold = float(profile.get("highlight_threshold", 60))
    suggest_no_jobs = bool(profile.get("suggest_watch_when_no_jobs_yet", True))

    for c in companies:
        c.score = round(100.0 * c.score_breakdown["_raw"] / max_raw, 1)
        c.highlighted = c.score >= threshold
        # Suggest watching companies that fit the profile (domain or AI) but
        # don't have matching jobs yet — hiring lags funding by a few weeks.
        fits = bool(c.domains) or c.ai_signal
        c.suggest_watch = suggest_no_jobs and fits and not c.matched_jobs


def sort_companies(companies: list[Company]) -> list[Company]:
    return sorted(companies, key=lambda c: c.score, reverse=True)
