"""Builders for synthetic RSS 2.0 feeds used in tests (never the real source)."""

import xml.sax.saxutils as sax

_HEAD = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<rss xmlns:content="http://purl.org/rss/1.0/modules/content/" '
    'xmlns:himalayasJobs="https://himalayas.app/ns/jobs" version="2.0">'
    "<channel><title>Remote jobs</title><link>https://example.test</link>"
)

_TAIL = "</channel></rss>"


def esc(value: str) -> str:
    return sax.escape(value)


def cdata(value: str) -> str:
    """CDATA content is raw text; escaping would corrupt the sample."""
    return f"<![CDATA[{value}]]>"


def item(
    title: str,
    url: str,
    guid: str | None = None,
    pubdate: str = "Tue, 18 Aug 2026 18:11:59 GMT",
    description: str | None = None,
    content: str | None = None,
    location: str | None = None,
    company: str | None = None,
    empty_desc: bool = False,
) -> str:
    body = f"<title>{cdata(title)}</title>"
    body += f"<link>{esc(url)}</link>"
    if guid:
        body += f"<guid isPermaLink=\"true\">{esc(guid)}</guid>"
    if pubdate:
        body += f"<pubDate>{esc(pubdate)}</pubDate>"
    if company:
        body += f"<himalayasJobs:companyName>{esc(company)}</himalayasJobs:companyName>"
    if location:
        body += f"<himalayasJobs:locationRestriction>{esc(location)}</himalayasJobs:locationRestriction>"
    if description:
        body += f"<description>{cdata(description)}</description>"
    if content:
        body += f"<content:encoded>{cdata(content)}</content:encoded>"
    if empty_desc:
        body += "<description/>"
    return f"<item>{body}</item>"


def build_feed(*items: str) -> str:
    return _HEAD + "".join(items) + _TAIL


JOB_A = item(
    title="Python Backend Engineer",
    url="https://example.test/companies/acme/jobs/python-backend-engineer",
    guid="https://example.test/companies/acme/jobs/python-backend-engineer",
    location="Remote",
    description="Backend work",
    content="<p>Build APIs</p>",
)
JOB_B = item(
    title="Frontend Developer",
    url="https://example.test/companies/globex/jobs/frontend-developer",
    guid="https://example.test/companies/globex/jobs/frontend-developer",
    location="United States",
    description="UI work",
    content="<p>Build UIs</p>",
)

DEFAULT_FEED = build_feed(JOB_A, JOB_B)
EMPTY_FEED = build_feed()
MALFORMED_XML = "<rss><channel>no closing tag"
NOT_RSS = "<html><body>hello</body></html>"

FEED_NO_GUID = build_feed(
    item(
        title="No Guid Job",
        url="https://example.test/companies/acme/jobs/no-guid",
        guid=None,
    )
)

FEED_MISSING_TITLE = build_feed(
    item(
        title="",
        url="https://example.test/companies/acme/jobs/broken",
        guid="broken-1",
    ),
    JOB_A,
)

FEED_MISSING_URL = build_feed(
    item(
        title="No Url",
        url="",
        guid="no-url-1",
    ),
    JOB_B,
)

ATOM_FEED = (
    '<?xml version="1.0"?>'
    '<feed xmlns="http://www.w3.org/2005/Atom">'
    "<title>Remote jobs</title>"
    '<entry>'
    "<title>Atom Role</title>"
    '<link href="https://example.test/atom-role"/>'
    "<id>https://example.test/atom-role</id>"
    "<updated>2026-08-18T18:00:00Z</updated>"
    "</entry>"
    "</feed>"
)