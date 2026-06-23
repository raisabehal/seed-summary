"""End-to-end weekly run: gather funding signals → aggregate → enrich with
hiring + domains + AI signal → score → persist → render email + dashboard."""
from __future__ import annotations

import logging
import os
from datetime import date
from typing import Any

from . import aggregate, categorize, report, scoring, store
from .config import Config, load_config
from .hiring.detect import detect_and_fetch
from .http import Http
from .models import Company
from .sources.rss import fetch_rss_feeds
from .sources.vc_portfolios import fetch_vc_portfolios

log = logging.getLogger("seedsummary.pipeline")


def gather_companies(cfg: Config, http: Http) -> list[Company]:
    sources = cfg.sources
    events = fetch_rss_feeds(sources.get("rss_feeds", []), http=http)
    log.info("Collected %d funding events from RSS", len(events))

    companies = aggregate.merge_events(events)
    companies = aggregate.filter_by_stage(companies, cfg.profile)

    # Best-effort VC portfolio attribution.
    try:
        attribution = fetch_vc_portfolios(sources.get("vc_portfolios", []), http)
        aggregate.apply_vc_attribution(companies, attribution)
    except Exception as exc:  # noqa: BLE001
        log.warning("VC attribution skipped: %s", exc)

    return companies


def enrich_company(company: Company, cfg: Config, http: Http) -> None:
    company.jobs = detect_and_fetch(company, http)
    categorize.enrich(company, cfg.profile)


def run(root=None, *, send: bool = True) -> dict[str, Any]:
    cfg = load_config(root) if root else load_config()
    http = Http.from_config(cfg.sources.get("http", {}))
    today = date.today()

    companies = gather_companies(cfg, http)
    for c in companies:
        enrich_company(c, cfg, http)

    # Also refresh hiring for watchlist companies even if they didn't raise
    # again this week, so we can flag NEW roles.
    watched = _load_watchlist_companies(cfg, http, existing={c.slug for c in companies})
    companies.extend(watched)

    scoring.score_batch(companies, cfg.profile)
    companies = scoring.sort_companies(companies)

    # Persist + diff against previous run for "new jobs" detection.
    fname = store.run_filename(today)
    prev = store.load_previous_run(cfg.data_dir, exclude=fname)
    store.save_run(cfg.data_dir, companies, today)

    watchlist_updates = _watchlist_updates(cfg, companies, prev)

    # Render outputs.
    repo = os.environ.get("GITHUB_REPOSITORY", "raisabehal/seed-summary")
    dashboard_url = os.environ.get("DASHBOARD_URL", "")
    report.build_dashboard(
        companies, generated_at=today.isoformat(), site_dir=cfg.site_dir, repo=repo
    )
    source_names = [f["name"] for f in cfg.sources.get("rss_feeds", []) if f.get("enabled", True)]
    html = report.render_email(
        companies,
        generated_at=today.isoformat(),
        watchlist_updates=watchlist_updates,
        dashboard_url=dashboard_url,
        sources=source_names,
    )
    (cfg.site_dir / "email-preview.html").write_text(html, encoding="utf-8")

    sent = False
    if send:
        subject = f"🌱 Seed Summary — {len([c for c in companies if c.highlighted])} hot leads · {today.isoformat()}"
        sent = report.send_email(html, subject)

    return {
        "companies": len(companies),
        "highlighted": len([c for c in companies if c.highlighted]),
        "watchlist_updates": len(watchlist_updates),
        "email_sent": sent,
    }


def _load_watchlist_companies(cfg: Config, http: Http, existing: set[str]) -> list[Company]:
    """Rebuild Company objects for watchlist entries not already in this week's
    funding batch, and fetch their current jobs."""
    out: list[Company] = []
    for entry in (cfg.watchlist.get("companies") or []):
        slug = entry.get("slug")
        if not slug or slug in existing:
            continue
        c = Company(name=entry.get("name", slug), slug=slug)
        ats = entry.get("ats") or {}
        if ats.get("provider") and ats.get("token"):
            c.ats = {"provider": ats["provider"], "token": ats["token"]}
        c.blurb = entry.get("notes", "")
        enrich_company(c, cfg, http)
        out.append(c)
    return out


def _watchlist_updates(cfg: Config, companies: list[Company], prev) -> list[dict[str, Any]]:
    watched_slugs = {e.get("slug") for e in (cfg.watchlist.get("companies") or [])}
    updates = []
    for c in companies:
        if c.slug not in watched_slugs:
            continue
        new_jobs = store.new_jobs_since(prev, c)
        updates.append({
            "name": c.name,
            "slug": c.slug,
            "stage": c.stage,
            "score": c.score,
            "highlighted": c.highlighted,
            "domains": c.domains,
            "ai_signal": c.ai_signal,
            "new_jobs": [j.__dict__ for j in new_jobs],
        })
    return updates
