"""Shared normalization helpers and the canonical ``NormalizedJob`` model."""

import hashlib
import html
import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.time import utc_now
from app.ingestion.parser import RawJob

_WHITESPACE = re.compile(r"\s+")
_TAGS = re.compile(r"<[^>]+>")


def clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = _WHITESPACE.sub(" ", value).strip()
    return cleaned or None


def to_plain_text(value: str | None) -> str | None:
    """Strip HTML tags from a rich-text description."""
    if value is None:
        return None
    text = _TAGS.sub(" ", value)
    text = html.unescape(text)
    text = _WHITESPACE.sub(" ", text).strip()
    return text or None


def company_from_url_slug(url: str | None) -> str | None:
    """Derive a display company name from a ``/companies/<slug>/`` URL path."""
    if not url:
        return None
    match = re.search(r"/companies/([^/]+)/", url)
    if not match:
        return None
    slug = match.group(1)
    return clean_text(re.sub(r"[-_]+", " ", slug).title())


def deterministic_fingerprint(source_name: str, title: str, company: str | None, url: str) -> str:
    """Stable ID for sources without a reliable external ID.

    Built from stable attributes only (never a random UUID) so the same job
    maps to the same ID across syncs.
    """
    payload = f"{source_name}|{title}|{company or ''}|{url}".strip().lower()
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"fp-{digest[:32]}"


class NormalizedJob(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: str
    title: str
    company: str | None = None
    location: str | None = None
    description: str | None = None
    url: str
    published_at: datetime | None = None
    first_seen_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)


def normalize_common(raw: RawJob, source_name: str) -> NormalizedJob:
    """Normalize a raw entry using shared rules (used by source adapters)."""
    company = clean_text(raw.company)
    url = (raw.url or "").strip()
    external_id = raw.external_id or deterministic_fingerprint(source_name, raw.title or "", company, url)
    return NormalizedJob(
        external_id=external_id,
        title=clean_text(raw.title) or "Untitled",
        company=company,
        location=clean_text(raw.location),
        description=to_plain_text(raw.content or raw.description),
        url=url,
        published_at=raw.published_at,
    )