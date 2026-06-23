"""Best-effort scraping of VC portfolio pages (a16z, Bessemer, NEA, GC, ...).

Portfolio pages list *all* portfolio companies, not recent rounds, so we use
them two ways:
  1. Investor attribution — if a funded company also appears in a VC's
     portfolio, we record that investor.
  2. A small confidence boost (a top-tier VC vetted them).

Layouts vary and many pages are JS-rendered, so extraction is intentionally
generic and never fatal: a source that yields nothing is logged and skipped.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from ..models import slugify

log = logging.getLogger("seedsummary.sources.vc")

_NOISE = {
    "portfolio", "companies", "about", "team", "news", "contact", "home",
    "menu", "search", "login", "subscribe", "privacy", "terms", "careers",
    "investments", "founders", "insights", "perspectives", "all", "read more",
}


def _candidate_names_from_html(html: str) -> set[str]:
    """Pull plausible company names from anchor text and common card markup."""
    soup = BeautifulSoup(html, "html.parser")
    names: set[str] = set()

    # Strategy 1: elements whose class hints at a portfolio card/name.
    for el in soup.select(
        "[class*='portfolio'] a, [class*='company'] , [class*='card'] h2, "
        "[class*='card'] h3, [class*='logo'] img"
    ):
        txt = el.get("alt") if el.name == "img" else el.get_text(" ", strip=True)
        _maybe_add(txt, names)

    # Strategy 2: anchor text that links into a /portfolio/ or /companies/ path.
    for a in soup.find_all("a", href=True):
        if re.search(r"/(portfolio|companies|company)/[\w\-]+", a["href"]):
            _maybe_add(a.get_text(" ", strip=True), names)

    return names


def _maybe_add(txt: str | None, names: set[str]) -> None:
    if not txt:
        return
    txt = re.sub(r"\s+", " ", txt).strip()
    low = txt.lower()
    if not (2 <= len(txt) <= 50):
        return
    if low in _NOISE or low.startswith(("http", "www")):
        return
    if not re.search(r"[A-Za-z]", txt):
        return
    names.add(txt)


def fetch_vc_portfolios(portfolios: list[dict[str, Any]], http) -> dict[str, set[str]]:
    """Returns {company_slug: {investor_name, ...}} for attribution."""
    attribution: dict[str, set[str]] = {}
    for vc in portfolios or []:
        if not vc.get("enabled", True):
            continue
        name, url = vc.get("name", ""), vc.get("url", "")
        if not url:
            continue
        resp = http.get(url)
        if resp is None or resp.status_code != 200:
            log.warning("VC portfolio %s unreachable", name)
            continue
        try:
            companies = _candidate_names_from_html(resp.text)
        except Exception as exc:  # noqa: BLE001
            log.warning("Failed to parse %s portfolio: %s", name, exc)
            continue
        for c in companies:
            attribution.setdefault(slugify(c), set()).add(name)
        log.info("VC %s: %d portfolio companies parsed", name, len(companies))
    return attribution
