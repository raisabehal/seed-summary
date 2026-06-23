from seedsummary.hiring import ats
from seedsummary.hiring.detect import candidate_tokens, detect_and_fetch
from seedsummary.models import Company
from conftest import FakeHttp, FakeResponse


def test_greenhouse_parsing():
    payload = {"jobs": [
        {"title": "Technical Program Manager", "absolute_url": "https://x/1",
         "location": {"name": "Remote"}, "updated_at": "2026-06-01T00:00:00Z",
         "departments": [{"name": "Engineering"}]},
    ]}
    http = FakeHttp({"boards-api.greenhouse.io": FakeResponse(json_data=payload)})
    jobs = ats.greenhouse("acme", http)
    assert len(jobs) == 1
    assert jobs[0].title == "Technical Program Manager"
    assert jobs[0].location == "Remote"
    assert jobs[0].department == "Engineering"
    assert jobs[0].posted == "2026-06-01"


def test_lever_parsing():
    payload = [
        {"text": "Product Manager", "hostedUrl": "https://l/1",
         "categories": {"location": "NYC", "team": "Product"}, "createdAt": 1750000000000},
    ]
    http = FakeHttp({"api.lever.co": FakeResponse(json_data=payload)})
    jobs = ats.lever("acme", http)
    assert jobs[0].title == "Product Manager"
    assert jobs[0].location == "NYC"
    assert jobs[0].posted is not None


def test_candidate_tokens():
    toks = candidate_tokens("Acme Health Inc")
    assert "acme" in toks
    assert any("acme" in t for t in toks)


def test_detect_and_fetch_probes_until_hit():
    payload = {"jobs": [{"title": "PM", "absolute_url": "u", "location": {"name": "R"},
                          "updated_at": "2026-06-01T00:00:00Z", "departments": []}]}
    # Only greenhouse returns data; lever/ashby/workable return 404.
    http = FakeHttp({
        "boards-api.greenhouse.io": FakeResponse(json_data=payload),
        "api.lever.co": FakeResponse(status_code=404),
    })
    c = Company(name="Acme")
    jobs = detect_and_fetch(c, http)
    assert jobs and c.ats["provider"] == "greenhouse"


def test_detect_uses_cached_ats():
    payload = {"jobs": []}
    http = FakeHttp({"boards-api.greenhouse.io": FakeResponse(json_data=payload)})
    c = Company(name="Acme", ats={"provider": "greenhouse", "token": "acme"})
    detect_and_fetch(c, http)
    # Should only have hit greenhouse with the cached token, not probed others.
    assert all("greenhouse" in url for url in http.calls)
