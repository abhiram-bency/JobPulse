from app.ingestion.normalizer import (
    clean_text,
    company_from_url_slug,
    deterministic_fingerprint,
    normalize_common,
    to_plain_text,
)
from app.ingestion.parser import RawJob


def test_fingerprint_is_stable():
    a = deterministic_fingerprint("Himalayas RSS", "Title", "Acme", "https://x.test")
    b = deterministic_fingerprint("Himalayas RSS", "Title", "Acme", "https://x.test")
    assert a == b
    assert a.startswith("fp-")


def test_fingerprint_changes_with_fields():
    a = deterministic_fingerprint("Himalayas RSS", "Title", "Acme", "https://x.test")
    b = deterministic_fingerprint("Himalayas RSS", "Title", "Other", "https://x.test")
    assert a != b


def test_fingerprint_is_deterministic_across_case():
    a = deterministic_fingerprint("Himalayas RSS", "Title", "Acme", "HTTPS://X.TEST")
    b = deterministic_fingerprint("himalayas rss", "title", "acme", "https://x.test")
    assert a == b


def test_to_plain_text_strips_html():
    assert to_plain_text("<p>Build <strong>APIs</strong> &amp; more</p>") == "Build APIs & more"


def test_to_plain_text_none():
    assert to_plain_text(None) is None


def test_clean_text_collapses_whitespace():
    assert clean_text("  Hello   world\n there ") == "Hello world there"


def test_company_from_url_slug():
    assert company_from_url_slug("https://example.test/companies/crowdstrike/jobs/x") == "Crowdstrike"
    assert company_from_url_slug("https://example.test/companies/my-company-co/jobs/x") == "My Company Co"
    assert company_from_url_slug("https://example.test/not-a-match") is None
    assert company_from_url_slug(None) is None


def test_normalize_common_uses_guid_as_external_id():
    raw = RawJob(
        title="Engineer",
        url="https://example.test/jobs/1",
        external_id="https://example.test/jobs/1",
        company="Acme",
        location="Remote",
        description="<p>desc</p>",
    )
    job = normalize_common(raw, "Himalayas RSS")
    assert job.external_id == "https://example.test/jobs/1"
    assert job.title == "Engineer"
    assert job.company == "Acme"
    assert job.description == "desc"
    assert job.url == "https://example.test/jobs/1"


def test_normalize_common_falls_back_to_fingerprint():
    raw = RawJob(title="Engineer", url="https://example.test/jobs/1", external_id=None)
    job = normalize_common(raw, "Himalayas RSS")
    assert job.external_id.startswith("fp-")
    assert job.external_id == deterministic_fingerprint(
        "Himalayas RSS", "Engineer", None, "https://example.test/jobs/1"
    )