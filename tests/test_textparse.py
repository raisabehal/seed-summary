from seedsummary import textparse as tp


def test_detect_stage():
    assert tp.detect_stage("raises $10M Series A") == "series a"
    assert tp.detect_stage("closes Series B round") == "series b"
    assert tp.detect_stage("lands pre-seed funding") == "pre-seed"
    assert tp.detect_stage("seed round announced") == "seed"
    assert tp.detect_stage("no stage here") == ""


def test_detect_amount():
    assert tp.detect_amount("raises $12M Series A") == "$12M"
    assert tp.detect_amount("secures $1.5 billion") == "$1.5B"
    assert tp.detect_amount("$500k pre-seed") == "$500K"
    assert tp.detect_amount("no money mentioned") == ""


def test_company_from_title():
    assert tp.company_from_title("Acme Health raises $12M Series A to scale") == "Acme Health"
    assert tp.company_from_title("Databricks secures huge round") == "Databricks"
    assert tp.company_from_title("Exclusive: Foo Bar lands seed funding") == "Foo Bar"
    assert tp.company_from_title("Some unrelated headline") == ""


def test_looks_like_funding():
    assert tp.looks_like_funding("Acme raises $10M Series A")
    assert tp.looks_like_funding("Beta closes seed round led by NEA")
    assert not tp.looks_like_funding("Apple announces new iPhone")


def test_detect_investors():
    inv = tp.detect_investors("raised $10M in a round led by Andreessen Horowitz and Bessemer.")
    assert "Andreessen Horowitz" in inv
    assert "Bessemer" in inv
