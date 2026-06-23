# 🌱 seed-summary

A weekly agent that scans for **recently funded** companies (pre-seed → Series B),
cross-checks whether they're **hiring** your target roles, scores them against
**your job profile**, emails you a digest, and lets you build a **watchlist** of
companies to keep monitoring for new roles in the coming weeks.

Built to run **for free** on GitHub Actions. No paid data APIs.

---

## What it does each week

```
GitHub Action (cron, Mondays 13:00 UTC)
  1. Gather funding signals   → RSS feeds (TechCrunch, FinSMEs, EU-Startups…)
                                + best-effort VC portfolio attribution (a16z, Bessemer, NEA, GC)
  2. Cross-check hiring        → probes each company's ATS (Greenhouse / Lever / Ashby / Workable)
                                  public job-board API for open roles
  3. Categorize + score        → domain (health / analytics), AI signal, matching roles,
                                  funding recency, stage → a 0–100 priority score
  4. Diff vs last week         → flags NEW roles at companies on your watchlist
  5. Deliver                   → HTML email digest + a dashboard published to GitHub Pages
  6. Watchlist                 → pick companies in the dashboard → opens a prefilled GitHub
                                  Issue → a second workflow merges them into config/watchlist.yml
```

Hiring usually lags funding by 2–3 weeks, so companies that fit your profile but
have **no matching roles yet** are surfaced under *"Worth watching"* and
suggested for your watchlist — exactly the lead time you asked for.

---

## Why these sources

| Need | Source | Why |
|------|--------|-----|
| Recent funding | **RSS feeds** (TechCrunch et al.) | Free, structured-enough, updated continuously. The primary signal. |
| Investor attribution | **VC portfolio pages** | Free; confirms top-tier backing. Best-effort (layouts vary / JS-rendered) so failures are non-fatal. |
| Hiring | **ATS public APIs** | Greenhouse/Lever/Ashby/Workable expose free JSON job boards — far more reliable than scraping LinkedIn, and ToS-friendly. |

Crunchbase/Dealroom are intentionally **not** used (paid). You can add any extra
RSS feed in `config/sources.yml`.

---

## One-time setup

### 1. Enable GitHub Pages
Repo **Settings → Pages → Source: GitHub Actions**. After the first run your
dashboard lives at `https://<you>.github.io/seed-summary/`.

### 2. Tell the email where the dashboard is
Repo **Settings → Secrets and variables → Actions → Variables**, add:
- `DASHBOARD_URL = https://<you>.github.io/seed-summary/`

### 3. Configure email (SMTP)
Add these **Secrets** (Gmail example — use an [App Password](https://support.google.com/accounts/answer/185833), not your login):

| Secret | Example |
|--------|---------|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | `you@gmail.com` |
| `SMTP_PASSWORD` | `your-app-password` |
| `EMAIL_FROM` | `you@gmail.com` |
| `EMAIL_TO` | `you@gmail.com` (comma-separated for multiple) |

If SMTP isn't configured the run still succeeds — it just builds the dashboard
and `site/email-preview.html` without sending (handy for testing).

### 4. Tune your profile
Edit **`config/profile.yml`** — target roles (TPM, engagement, delivery, PM),
domains (health, analytics), AI keywords, target stages, and the scoring
`weights`. Everything is commented.

### 5. Run it
Actions → **Weekly scan** → *Run workflow* (set `send_email: false` for a dry
run). Or wait for the Monday cron.

---

## Managing your watchlist

1. Open the dashboard, tick the companies you want to monitor, click **⭐ Save to watchlist**.
2. That opens a prefilled GitHub Issue (label `watchlist`). Submit it.
3. The **Watchlist update** workflow merges them into `config/watchlist.yml`,
   comments, and closes the issue.
4. Every following week the digest shows a **📌 Your watchlist** section with any
   **NEW** roles posted since the last run.

You can also hand-edit `config/watchlist.yml`.

---

## How the score works

Each component is computed `0..1`, multiplied by its weight in `profile.yml`,
summed, multiplied by a stage factor, then **normalized to 0–100** across the
week's batch:

- `role_match` — has open jobs matching your target roles (× small seniority bonus)
- `domain_match` — operates in a target domain (health / analytics)
- `ai_signal` — building AI capabilities
- `funding_recency` — decays over the lookback window
- `hiring_volume` — number of relevant open roles (saturates at 5)
- `stage_fit` — per-stage multiplier

Companies at/above `highlight_threshold` are marked high-priority.

---

## Local development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q                      # run tests (fully offline, network mocked)
python -m seedsummary run --no-email --verbose   # real run, no email
```

Outputs land in `site/index.html`, `site/email-preview.html`, and
`data/run-<date>.json`.

> Live source calls (RSS/ATS) require outbound network and are exercised in
> CI / on GitHub Actions; the unit tests mock all HTTP so they run anywhere.

---

## Project layout

```
config/            profile.yml · sources.yml · watchlist.yml
seedsummary/
  sources/         rss.py · vc_portfolios.py        (funding signals)
  hiring/          ats.py · detect.py               (Greenhouse/Lever/Ashby/Workable)
  textparse.py     parse stage/amount/investors/company from headlines
  aggregate.py     merge events → companies, stage filter, VC attribution
  categorize.py    domains + AI signal + role matching
  scoring.py       priority score + normalization
  store.py         persist runs + week-over-week new-jobs diff
  report.py        render email + dashboard, send SMTP
  pipeline.py      orchestration   ·   __main__.py  CLI
  templates/       email.html.j2 · dashboard.html.j2
scripts/           update_watchlist.py
.github/workflows/ weekly-scan.yml · watchlist-update.yml · ci.yml
tests/             pytest suite (HTTP mocked)
```

## Limitations & honest caveats

- **RSS coverage isn't exhaustive** — it captures what those outlets report. Add
  more feeds in `config/sources.yml` to widen the net.
- **ATS token detection is heuristic** — it guesses a company's board token from
  its name. Misses are possible; once a company is on your watchlist you can pin
  its exact `ats: {provider, token}` in `watchlist.yml`.
- **VC portfolio scrapers are best-effort** — pages change and some are
  JS-rendered; they enrich but never block a run.
