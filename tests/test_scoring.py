from seedsummary import categorize, scoring
from seedsummary.models import Company, Job

PROFILE = {
    "target_roles": [
        {"name": "TPM", "match": ["technical program manager", "tpm"]},
        {"name": "Product Manager", "match": ["product manager"]},
    ],
    "seniority_bonus_keywords": ["senior", "head"],
    "target_domains": [
        {"name": "Health", "weight": 1.0, "match": ["health", "clinical"]},
        {"name": "Analytics / Data", "weight": 1.0, "match": ["analytics", "data platform"]},
    ],
    "ai_signal": {"weight": 1.0, "match": ["ai", "machine learning"]},
    "target_stages": ["seed", "series a", "series b"],
    "stage_weights": {"seed": 0.8, "series a": 1.0, "series b": 1.0},
    "weights": {"role_match": 4.0, "domain_match": 2.5, "ai_signal": 2.0,
                "funding_recency": 1.0, "hiring_volume": 1.0, "stage_fit": 0.5},
    "highlight_threshold": 60,
    "funding_lookback_days": 30,
    "suggest_watch_when_no_jobs_yet": True,
}


def _company(name, blurb, jobs, stage="series a", funded_on=None):
    c = Company(name=name, blurb=blurb, stage=stage, funded_on=funded_on)
    c.jobs = jobs
    categorize.enrich(c, PROFILE)
    return c


def test_health_ai_with_tpm_beats_generic():
    strong = _company("HealthAI", "AI clinical health platform",
                       [Job(title="Senior Technical Program Manager")])
    weak = _company("Widgets Co", "we make widgets", [Job(title="Sales Rep")])
    scoring.score_batch([strong, weak], PROFILE)
    assert strong.score > weak.score
    assert strong.highlighted
    assert "Health" in strong.domains
    assert strong.ai_signal
    assert strong.matched_jobs and strong.matched_jobs[0].matched_role == "TPM"


def test_suggest_watch_when_fit_but_no_jobs():
    c = _company("Analytics AI", "data platform analytics with machine learning", [])
    scoring.score_batch([c], PROFILE)
    assert c.suggest_watch
    assert not c.matched_jobs


def test_normalization_to_100():
    a = _company("A", "health ai", [Job(title="TPM")])
    b = _company("B", "nothing", [])
    scoring.score_batch([a, b], PROFILE)
    assert a.score == 100.0
    assert 0 <= b.score <= 100
