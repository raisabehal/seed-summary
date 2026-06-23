from seedsummary import aggregate
from seedsummary.models import FundingEvent
from seedsummary.sources.rss import fetch_rss_feeds
from conftest import FakeHttp, FakeResponse

SAMPLE_FEED = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <item>
    <title>Acme Health raises $12M Series A led by NEA</title>
    <link>https://techcrunch.com/acme</link>
    <description>Acme Health, a clinical AI platform, raised $12M.</description>
    <pubDate>Mon, 22 Jun 2026 10:00:00 GMT</pubDate>
  </item>
  <item>
    <title>Apple announces new iPhone</title>
    <link>https://techcrunch.com/apple</link>
    <description>Not funding news.</description>
    <pubDate>Mon, 22 Jun 2026 10:00:00 GMT</pubDate>
  </item>
</channel></rss>"""


def test_fetch_rss_filters_non_funding():
    http = FakeHttp({"feed": FakeResponse(content=SAMPLE_FEED.encode())})
    feeds = [{"name": "Test", "url": "https://example.com/feed", "enabled": True}]
    events = fetch_rss_feeds(feeds, http=http)
    assert len(events) == 1
    e = events[0]
    assert e.company_name == "Acme Health"
    assert e.stage == "series a"
    assert e.amount == "$12M"


def test_merge_events_dedupes():
    events = [
        FundingEvent(company_name="Acme", stage="seed", source="A", url="u1"),
        FundingEvent(company_name="Acme", amount="$5M", source="B", url="u2"),
    ]
    companies = aggregate.merge_events(events)
    assert len(companies) == 1
    c = companies[0]
    assert c.stage == "seed"
    assert c.amount == "$5M"
    assert set(c.sources) == {"A", "B"}
    assert set(c.urls) == {"u1", "u2"}


def test_filter_by_stage_keeps_unknown():
    profile = {"target_stages": ["seed", "series a"]}
    companies = aggregate.merge_events([
        FundingEvent(company_name="Seed Co", stage="seed"),
        FundingEvent(company_name="Late Co", stage="series d"),
        FundingEvent(company_name="Unknown Co", stage=""),
    ])
    kept = {c.name for c in aggregate.filter_by_stage(companies, profile)}
    assert "Seed Co" in kept
    assert "Unknown Co" in kept
    assert "Late Co" not in kept
