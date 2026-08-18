from app.ingestion.parser import RSSParser, RSSParseError, parse_rfc822_or_iso
from tests.fixtures.rss import (
    ATOM_FEED,
    DEFAULT_FEED,
    EMPTY_FEED,
    JOB_A,
    MALFORMED_XML,
    NOT_RSS,
    build_feed,
    item,
)


def test_parses_valid_rss():
    result = RSSParser().parse(DEFAULT_FEED)
    assert len(result.items) == 2
    first = result.items[0]
    assert first.title == "Python Backend Engineer"
    assert first.url == "https://example.test/companies/acme/jobs/python-backend-engineer"
    assert first.external_id == first.url
    assert first.published_at is not None
    assert first.description == "Backend work"
    assert first.content == "<p>Build APIs</p>"


def test_parses_empty_feed():
    result = RSSParser().parse(EMPTY_FEED)
    assert result.items == []


def test_malformed_xml_raises():
    try:
        RSSParser().parse(MALFORMED_XML)
    except RSSParseError:
        return
    raise AssertionError("expected RSSParseError")


def test_unrecognized_root_raises():
    try:
        RSSParser().parse(NOT_RSS)
    except RSSParseError:
        return
    raise AssertionError("expected RSSParseError")


def test_atom_feed():
    result = RSSParser().parse(ATOM_FEED)
    assert len(result.items) == 1
    entry = result.items[0]
    assert entry.title == "Atom Role"
    assert entry.url == "https://example.test/atom-role"
    assert entry.external_id == "https://example.test/atom-role"


def test_namespace_extra_fields():
    feed = build_feed(
        item(
            title="X",
            url="https://example.test/companies/acme/jobs/x",
            guid="x-1",
            location="Brazil",
            company="Acme",
        )
    )
    parser = RSSParser(
        extra_fields=[
            ("https://himalayas.app/ns/jobs", "companyName", "company"),
            ("https://himalayas.app/ns/jobs", "locationRestriction", "location"),
        ]
    )
    result = parser.parse(feed)
    assert result.items[0].company == "Acme"
    assert result.items[0].location == "Brazil"


def test_optional_fields_missing():
    feed = build_feed(
        item(
            title="Minimal",
            url="https://example.test/minimal",
            guid="minimal-1",
            pubdate=None,
            description=None,
            content=None,
            empty_desc=True,
        )
    )
    result = RSSParser().parse(feed)
    assert result.items[0].title == "Minimal"
    assert result.items[0].published_at is None


def test_rfc822_date_parsing():
    parsed = parse_rfc822_or_iso("Tue, 18 Aug 2026 18:11:59 GMT")
    assert parsed is not None
    assert parsed.year == 2026


def test_iso_date_parsing():
    parsed = parse_rfc822_or_iso("2026-08-18T18:11:59Z")
    assert parsed is not None


def test_invalid_date_returns_none():
    assert parse_rfc822_or_iso("not a date") is None
    assert parse_rfc822_or_iso(None) is None