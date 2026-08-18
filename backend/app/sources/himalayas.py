"""Himalayas RSS adapter.

Himalayas (https://himalayas.app/jobs/rss) is an open, public RSS 2.0 feed of
remote jobs. It requires no API key or authentication, which makes it the
ideal low-risk source for this challenge's live demo.

Feed quirk: ``himalayasJobs:companyName`` contains the literal placeholder
``name`` and ``himalayasJobs:companyLogo`` contains ``thumbnail_url``. Real
company names are therefore derived from the ``/companies/<slug>/`` URL path.
"""

from app.ingestion.normalizer import NormalizedJob, company_from_url_slug, normalize_common
from app.ingestion.parser import ParseResult, RSSParser
from app.sources.base import JobSource

_HIMALAYAS_NS = "https://himalayas.app/ns/jobs"

_EXTRA_FIELDS = [
    (_HIMALAYAS_NS, "companyName", "company"),
    (_HIMALAYAS_NS, "locationRestriction", "location"),
    (_HIMALAYAS_NS, "expiryDate", "expiry_date"),
]

_PLACEHOLDER_COMPANY = {"name", ""}


class HimalayasRSSSource(JobSource):
    def __init__(self, *, feed_url: str, fetcher, name: str = "Himalayas RSS") -> None:
        super().__init__(name=name, source_type="rss", feed_url=feed_url, fetcher=fetcher)
        self._parser = RSSParser(extra_fields=_EXTRA_FIELDS)

    def parse(self, payload: str) -> ParseResult:
        return self._parser.parse(payload)

    def normalize(self, raw) -> NormalizedJob:
        normalized = normalize_common(raw, self.name)
        if normalized.company in _PLACEHOLDER_COMPANY or not normalized.company:
            normalized.company = company_from_url_slug(raw.url)
        return normalized