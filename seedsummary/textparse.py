"""Heuristics for pulling structured funding facts out of free-text headlines
and article summaries. Deliberately conservative: when unsure, leave blank."""
from __future__ import annotations

import re

# Order matters: check the most specific stages first.
_STAGE_PATTERNS = [
    ("series b", r"series[\s\-]?b\b"),
    ("series a", r"series[\s\-]?a\b"),
    ("pre-seed", r"pre[\s\-]?seed"),
    ("seed", r"\bseed\b"),
]

_AMOUNT_RE = re.compile(
    r"(?:US)?\$?\s?(\d+(?:\.\d+)?)\s?(million|billion|m|bn|b|k)\b",
    re.IGNORECASE,
)

# "... in a round led by X" / "led by X and Y" / "from X, Y and Z"
_LED_BY_RE = re.compile(r"led by ([^.;]+?)(?:[.;]|$|, with| with | to | as )", re.IGNORECASE)
_FROM_RE = re.compile(r"(?:backed by|investors include|with participation from|from) ([^.;]+?)(?:[.;]|$)", re.IGNORECASE)

_FUNDING_HINTS = re.compile(
    r"\b(raises?|raised|secures?|secured|closes?|closed|lands?|landed|"
    r"funding|round|investment|backs?|backed|nets?|netted)\b",
    re.IGNORECASE,
)


def looks_like_funding(text: str) -> bool:
    """Cheap gate so we ignore non-funding articles in general feeds."""
    if not text:
        return False
    has_money = bool(_AMOUNT_RE.search(text))
    has_stage = any(re.search(p, text, re.IGNORECASE) for _, p in _STAGE_PATTERNS)
    return bool(_FUNDING_HINTS.search(text)) and (has_money or has_stage)


def detect_stage(text: str) -> str:
    text = text or ""
    for name, pattern in _STAGE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return name
    return ""


def detect_amount(text: str) -> str:
    m = _AMOUNT_RE.search(text or "")
    if not m:
        return ""
    num, unit = m.group(1), m.group(2).lower()
    unit_map = {"million": "M", "m": "M", "billion": "B", "bn": "B", "b": "B", "k": "K"}
    return f"${num}{unit_map.get(unit, unit.upper())}"


def detect_investors(text: str) -> list[str]:
    text = text or ""
    investors: list[str] = []
    for rx in (_LED_BY_RE, _FROM_RE):
        m = rx.search(text)
        if m:
            chunk = m.group(1)
            parts = re.split(r",| and | & ", chunk)
            for p in parts:
                p = p.strip(" .")
                # Keep plausible firm names (Title Case-ish, short).
                if 2 <= len(p) <= 40 and p[:1].isupper():
                    investors.append(p)
    # De-dupe, preserve order.
    seen, out = set(), []
    for inv in investors:
        if inv.lower() not in seen:
            seen.add(inv.lower())
            out.append(inv)
    return out


# Company name extraction from a headline like:
#   "Acme Health raises $12M Series A to ..."
_COMPANY_FROM_TITLE_RE = re.compile(
    r"^(.*?)\s+(?:raises?|raised|secures?|secured|closes?|closed|lands?|landed|nets?|netted|gets?|bags?)\b",
    re.IGNORECASE,
)


def company_from_title(title: str) -> str:
    if not title:
        return ""
    m = _COMPANY_FROM_TITLE_RE.match(title.strip())
    if m:
        name = m.group(1).strip(" :–—-")
        # Strip leading boilerplate some feeds add.
        name = re.sub(r"^(exclusive|breaking|update)\s*[:\-]\s*", "", name, flags=re.IGNORECASE)
        return name.strip()
    return ""
