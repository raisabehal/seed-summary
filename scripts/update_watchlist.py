"""Parse a GitHub issue body (created from the dashboard) and merge the
selected companies into config/watchlist.yml.

Invoked by the `watchlist-update` workflow with the issue body on stdin or in
the ISSUE_BODY env var. The body contains a fenced ```yaml block listing
companies as:

    - slug: acme-health
      name: Acme Health
      ats: {provider: greenhouse, token: acmehealth}
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
WATCHLIST = ROOT / "config" / "watchlist.yml"


def extract_yaml_block(body: str) -> str:
    m = re.search(r"```ya?ml\s*\n(.*?)```", body, re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else ""


def parse_entries(block: str) -> list[dict]:
    if not block.strip():
        return []
    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        return []
    if isinstance(data, dict) and "companies" in data:
        data = data["companies"]
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if isinstance(item, dict) and item.get("slug"):
            out.append(item)
    return out


def merge(entries: list[dict]) -> int:
    current = {}
    if WATCHLIST.exists():
        loaded = yaml.safe_load(WATCHLIST.read_text(encoding="utf-8")) or {}
        for c in (loaded.get("companies") or []):
            if c.get("slug"):
                current[c["slug"]] = c

    added = 0
    today = date.today().isoformat()
    for e in entries:
        slug = e["slug"]
        if slug in current:
            continue
        entry = {"slug": slug, "name": e.get("name", slug), "added": today}
        ats = e.get("ats") or {}
        if ats.get("provider") and ats.get("token"):
            entry["ats"] = {"provider": ats["provider"], "token": ats["token"]}
        if e.get("notes"):
            entry["notes"] = e["notes"]
        current[slug] = entry
        added += 1

    payload = {"companies": sorted(current.values(), key=lambda c: c["slug"])}
    header = (
        "# Companies you are actively monitoring for NEW relevant roles each week.\n"
        "# Managed by the dashboard + watchlist-update workflow; hand-edits are fine.\n"
    )
    WATCHLIST.write_text(header + yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return added


def main() -> int:
    body = os.environ.get("ISSUE_BODY")
    if body is None:
        body = sys.stdin.read()
    entries = parse_entries(extract_yaml_block(body))
    if not entries:
        print("No valid watchlist entries found in issue body.")
        return 0
    added = merge(entries)
    print(f"Added {added} new compan{'y' if added == 1 else 'ies'} to the watchlist ({len(entries)} requested).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
