"""Offline end-to-end smoke test: stub out the network sources and verify the
pipeline produces a dashboard, email preview, and a persisted run file."""
import json
from pathlib import Path

from seedsummary import pipeline
from seedsummary.config import load_config
from seedsummary.models import Company, Job


def test_pipeline_end_to_end(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parent.parent

    # Stub funding gathering with two companies.
    def fake_gather(cfg, http):
        a = Company(name="HealthAI", blurb="clinical AI health platform",
                    stage="series a", funded_on="2026-06-20", urls=["https://news/1"])
        b = Company(name="Widgets", blurb="we make widgets", stage="seed")
        return [a, b]

    def fake_enrich(company, cfg, http):
        if company.name == "HealthAI":
            company.jobs = [Job(title="Technical Program Manager", url="https://j/1", location="Remote")]
        from seedsummary import categorize
        categorize.enrich(company, cfg.profile)

    monkeypatch.setattr(pipeline, "gather_companies", fake_gather)
    monkeypatch.setattr(pipeline, "enrich_company", fake_enrich)
    # Point config at a temp working dir copy so we don't write into the repo.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(pipeline, "load_config", lambda *a, **k: load_config(root))

    # Redirect data/site to tmp by monkeypatching the Config dirs via env.
    cfg = load_config(root)
    monkeypatch.setattr(type(cfg), "data_dir", property(lambda self: _mk(tmp_path / "data")))
    monkeypatch.setattr(type(cfg), "site_dir", property(lambda self: _mk(tmp_path / "site", sub="data")))

    result = pipeline.run(send=False)

    assert result["companies"] == 2
    assert (tmp_path / "site" / "index.html").exists()
    assert (tmp_path / "site" / "email-preview.html").exists()
    latest = json.loads((tmp_path / "data" / "latest.json").read_text())
    names = [c["name"] for c in latest["companies"]]
    # HealthAI should rank first (AI + health + matching TPM role).
    assert names[0] == "HealthAI"


def _mk(p: Path, sub: str | None = None) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    if sub:
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p
