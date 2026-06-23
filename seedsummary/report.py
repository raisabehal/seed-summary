"""Render the weekly email and the static dashboard, and send the email."""
from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import Company

log = logging.getLogger("seedsummary.report")
TEMPLATES = Path(__file__).resolve().parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )


def render_email(
    companies: list[Company],
    *,
    generated_at: str,
    watchlist_updates: list[dict[str, Any]],
    dashboard_url: str,
    sources: list[str],
    top_n: int = 15,
) -> str:
    top = companies[:top_n]
    highlighted = [c for c in companies if c.highlighted]
    suggested = [c for c in companies if c.suggest_watch and c not in top][:10]
    tmpl = _env().get_template("email.html.j2")
    return tmpl.render(
        generated_at=generated_at,
        companies=companies,
        top=top,
        highlighted=highlighted,
        suggested=suggested,
        watchlist_updates=watchlist_updates,
        dashboard_url=dashboard_url,
        sources=sources,
    )


def build_dashboard(
    companies: list[Company],
    *,
    generated_at: str,
    site_dir: Path,
    repo: str,
) -> Path:
    payload = {
        "generated_at": generated_at,
        "companies": [c.to_dict() for c in companies],
    }
    # Write data file (handy for debugging / external consumers)…
    (site_dir / "data").mkdir(parents=True, exist_ok=True)
    (site_dir / "data" / "latest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    # …and embed it inline so the page is self-contained on GitHub Pages.
    tmpl = _env().get_template("dashboard.html.j2")
    html = tmpl.render(
        generated_at=generated_at,
        companies=companies,
        payload_json=json.dumps(payload),
        repo=repo,
    )
    out = site_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out


def send_email(html: str, subject: str) -> bool:
    """Send via SMTP using env vars. Returns False (without raising) if SMTP is
    not configured, so a dry run still produces the dashboard + data files.

    Required env: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO
    Optional:     SMTP_PORT (default 587)
    """
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("EMAIL_FROM", user or "")
    recipients = os.environ.get("EMAIL_TO", "")
    port = int(os.environ.get("SMTP_PORT", "587"))

    if not (host and user and password and sender and recipients):
        log.warning("SMTP not fully configured — skipping email send (dry run).")
        return False

    to_list = [r.strip() for r in recipients.split(",") if r.strip()]
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText("Your weekly seed-summary is best viewed as HTML.", "plain"))
    msg.attach(MIMEText(html, "html"))

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, password)
        server.sendmail(sender, to_list, msg.as_string())
    log.info("Email sent to %s", to_list)
    return True
