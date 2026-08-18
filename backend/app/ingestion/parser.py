"""Generic RSS 2.0 / Atom feed parsing into source-agnostic raw entries.

Uses only the stdlib (xml.etree) so it is easy to test and has no parser
dependency. Source-specific namespaces are supplied by the source adapter
via ``extra_fields`` (namespace URI, local tag, target field).
"""

import email.utils
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

ATOM_NS = "{http://www.w3.org/2005/Atom}"
CONTENT_NS = "{http://purl.org/rss/1.0/modules/content/}"
DC_NS = "{http://purl.org/dc/elements/1.1/}"


class RSSParseError(Exception):
    """Raised when the payload is not a parseable RSS/Atom document."""


@dataclass
class RawJob:
    title: str | None = None
    url: str | None = None
    external_id: str | None = None
    published_at: datetime | None = None
    description: str | None = None
    content: str | None = None
    company: str | None = None
    location: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    items: list[RawJob] = field(default_factory=list)
    feed_title: str | None = None


def parse_rfc822_or_iso(value: str | None) -> datetime | None:
    """Parse RFC 822 (RSS pubDate) or ISO-8601 dates, else None."""
    if not value:
        return None
    text = value.strip()
    for attempt in (email.utils.parsedate_to_datetime, _from_iso):
        try:
            parsed = attempt(text)
        except (ValueError, TypeError, IndexError, OverflowError):
            continue
        if parsed is None:
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    return None


def _from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class RSSParser:
    """Parses RSS 2.0 and Atom documents into ``RawJob`` items.

    ``extra_fields`` is a list of ``(namespace_uri, local_tag, target)`` tuples.
    ``target`` is ``"company"``, ``"location"`` or any other key (stored in
    ``RawJob.extra``).
    """

    def __init__(self, extra_fields: list[tuple[str, str, str]] | None = None) -> None:
        self._extra_fields: list[tuple[str, str, str]] = extra_fields or []

    def parse(self, text: str) -> ParseResult:
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            raise RSSParseError(f"malformed XML: {exc}") from exc

        if root.tag == "rss":
            return self._parse_rss(root)
        if root.tag == f"{ATOM_NS}feed":
            return self._parse_atom(root)
        raise RSSParseError(f"unrecognized root element: {root.tag!r}")

    # -- RSS 2.0 --------------------------------------------------------------

    def _parse_rss(self, root: ET.Element) -> ParseResult:
        channel = root.find("channel")
        if channel is None:
            raise RSSParseError("rss document missing <channel>")
        result = ParseResult(feed_title=_text(channel, "title"))
        for item in channel.findall("item"):
            result.items.append(self._parse_rss_item(item))
        return result

    def _parse_rss_item(self, item: ET.Element) -> RawJob:
        raw = RawJob(
            title=_text(item, "title"),
            url=_text(item, "link"),
            external_id=_text(item, "guid"),
            published_at=parse_rfc822_or_iso(_text(item, "pubDate")),
            description=_text(item, "description"),
            content=_text(item, f"{CONTENT_NS}encoded"),
            company=_text(item, f"{DC_NS}creator"),
        )
        for ns_uri, tag, target in self._extra_fields:
            value = _text(item, f"{{{ns_uri}}}{tag}")
            if not value:
                continue
            if target in {"company", "location"}:
                setattr(raw, target, value)
            else:
                raw.extra[target] = value
        return raw

    # -- Atom ------------------------------------------------------------------

    def _parse_atom(self, root: ET.Element) -> ParseResult:
        result = ParseResult(feed_title=_text(root, f"{ATOM_NS}title"))
        for entry in root.findall(f"{ATOM_NS}entry"):
            raw = RawJob(
                title=_text(entry, f"{ATOM_NS}title"),
                url=_atom_link(entry),
                external_id=_text(entry, f"{ATOM_NS}id"),
                published_at=parse_rfc822_or_iso(
                    _text(entry, f"{ATOM_NS}published") or _text(entry, f"{ATOM_NS}updated")
                ),
                description=_text(entry, f"{ATOM_NS}summary"),
                content=_text(entry, f"{ATOM_NS}content"),
                company=_text(entry, f"{DC_NS}creator"),
            )
            result.items.append(raw)
        return result


def _text(el: ET.Element, path: str) -> str | None:
    node = el.find(path)
    value = node.text if node is not None else None
    return value.strip() if value is not None else None


def _atom_link(entry: ET.Element) -> str | None:
    node = entry.find(f"{ATOM_NS}link")
    if node is None:
        return None
    href = node.get("href")
    return href.strip() if href else None