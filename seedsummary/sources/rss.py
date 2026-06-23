"""Funding signals from RSS/Atom feeds (TechCrunch, FinSMEs, etc.).

These are the most reliable free source. We parse each entry, keep only items
that look like funding announcements, and extract company/stage/amount.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import feedparser

from ..models import FundingEvent
from ..textparse import (
    company_from_title,
    detect_amount,
    detect_investors,
    detect_stage,
    looks_like_funding,
)

log = logging.getLogger("seedsummary.sources.rss")


def _entry_published_iso(entry: Any) -> str | None:
    for key in ("published_parsed", "updated_parsed"):
        tm = getattr(entry, key, None) or entry.get(key) if hasattr(entry, "get") else getattr(entry, key, None)
        if tm:
            try:
                return datetime(*tm[:6], tzinfo=timezone.utc).date().isoformat()
            except (TypeError, ValueError):
                continue
    return None


def fetch_rss_feeds(feeds: list[dict[str, Any]], http=None) -> list[FundingEvent]:
    """Parse each enabled feed into FundingEvents. `http` is optional; when
    provided we fetch bytes through the shared session, otherwise feedparser
    fetches directly (used in tests with local content)."""
    events: list[FundingEvent] = []
    for feed in feeds or []:
        if not feed.get("enabled", True):
            continue
        name, url = feed.get("name", url := feed.get("url", "")), feed.get("url", "")
        if not url:
            continue
        try:
            if http is not None:
                resp = http.get(url)
                if resp is None or resp.status_code != 200:
                    log.warning("Feed %s returned no content", name)
                    continue
                parsed = feedparser.parse(resp.content)
            else:
                parsed = feedparser.parse(url)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to parse feed %s: %s", name, exc)
            continue

        count = 0
        for entry in parsed.entries:
            title = getattr(entry, "title", "") or ""
            summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
            text = f"{title}. {summary}"
            if not looks_like_funding(text):
                continue
            company = company_from_title(title)
            if not company:
                continue
            events.append(
                FundingEvent(
                    company_name=company,
                    stage=detect_stage(text),
                    amount=detect_amount(text),
                    investors=detect_investors(text),
                    source=name,
                    url=getattr(entry, "link", "") or "",
                    published=_entry_published_iso(entry),
                    blurb=_clean(summary)[:600],
                )
            )
            count += 1
        log.info("RSS %s: %d funding items", name, count)
    return events


def _clean(html: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()
