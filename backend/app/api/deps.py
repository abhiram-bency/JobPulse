from functools import lru_cache

from fastapi import Depends

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.ingestion.fetcher import HTTPFetcher
from app.ingestion.service import SyncService
from app.sources.base import JobSource
from app.sources.himalayas import HimalayasRSSSource


@lru_cache
def _fetcher_instance() -> HTTPFetcher:
    settings = get_settings()
    return HTTPFetcher(
        timeout_seconds=settings.fetch_timeout_seconds,
        max_retries=settings.fetch_max_retries,
        base_backoff_seconds=settings.fetch_base_backoff_seconds,
        max_backoff_seconds=settings.fetch_max_backoff_seconds,
        max_retry_after_seconds=settings.fetch_max_retry_after_seconds,
        minimum_request_interval_seconds=settings.minimum_request_interval_seconds,
        user_agent=settings.himalayas_user_agent,
    )


def get_fetcher() -> HTTPFetcher:
    return _fetcher_instance()


def get_source(fetcher: HTTPFetcher = Depends(get_fetcher)) -> JobSource:
    settings = get_settings()
    return HimalayasRSSSource(
        feed_url=settings.himalayas_feed_url,
        fetcher=fetcher,
        name=settings.himalayas_source_name,
    )


def get_sync_service(
    source: JobSource = Depends(get_source),
    fetcher: HTTPFetcher = Depends(get_fetcher),
) -> SyncService:
    return SyncService(
        session_factory=SessionLocal,
        source=source,
        fetcher=fetcher,
        settings=get_settings(),
    )