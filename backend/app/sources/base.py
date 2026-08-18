"""JobSource abstraction.

A source owns the source-specific parts of the pipeline:
- fetch (raw bytes/text from its feed)
- parse (source payload -> generic RawJob entries)
- normalize (RawJob -> canonical NormalizedJob)

The ingestion service and the rest of the application never see
source-specific RSS/HTML structure. A future provider (e.g. RemoteOK)
only needs to implement this same interface.
"""

from abc import ABC, abstractmethod

from app.ingestion.fetcher import FetchResult, HTTPFetcher
from app.ingestion.normalizer import NormalizedJob
from app.ingestion.parser import ParseResult, RawJob


class JobSource(ABC):
    name: str
    source_type: str
    feed_url: str

    def __init__(
        self,
        *,
        name: str,
        source_type: str,
        feed_url: str,
        fetcher: HTTPFetcher,
    ) -> None:
        self.name = name
        self.source_type = source_type
        self.feed_url = feed_url
        self._fetcher = fetcher

    async def fetch(self) -> FetchResult:
        return await self._fetcher.fetch(self.feed_url)

    @abstractmethod
    def parse(self, payload: str) -> ParseResult:
        ...

    @abstractmethod
    def normalize(self, raw: RawJob) -> NormalizedJob:
        ...

    async def fetch_and_parse(self) -> ParseResult:
        result = await self.fetch()
        return self.parse(result.text)