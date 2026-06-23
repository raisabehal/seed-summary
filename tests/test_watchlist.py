import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("update_watchlist", ROOT / "scripts" / "update_watchlist.py")
uw = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uw)

ISSUE_BODY = """Add these companies to my seed-summary watchlist:

```yaml
- slug: acme-health
  name: Acme Health
  ats: {provider: greenhouse, token: acmehealth}
- slug: beta-data
  name: Beta Data
  ats: {provider: , token: }
```

_Submitted from the dashboard._
"""


def test_extract_and_parse():
    block = uw.extract_yaml_block(ISSUE_BODY)
    entries = uw.parse_entries(block)
    assert len(entries) == 2
    assert entries[0]["slug"] == "acme-health"
    assert entries[0]["ats"]["provider"] == "greenhouse"


def test_merge_writes_watchlist(tmp_path, monkeypatch):
    wl = tmp_path / "watchlist.yml"
    monkeypatch.setattr(uw, "WATCHLIST", wl)
    entries = uw.parse_entries(uw.extract_yaml_block(ISSUE_BODY))
    added = uw.merge(entries)
    assert added == 2
    data = yaml.safe_load(wl.read_text())
    slugs = {c["slug"] for c in data["companies"]}
    assert slugs == {"acme-health", "beta-data"}
    # Empty ats should be dropped.
    beta = next(c for c in data["companies"] if c["slug"] == "beta-data")
    assert "ats" not in beta
    # Re-merge is idempotent.
    assert uw.merge(entries) == 0
