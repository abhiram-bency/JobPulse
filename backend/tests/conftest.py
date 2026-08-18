"""Shared test infrastructure.

Environment is configured BEFORE any ``app`` module is imported so the whole
application (DB engine, settings cache) is built against a local SQLite file.
All HTTP traffic is intercepted by an ``httpx.MockTransport`` — tests never
touch the real Himalayas feed.
"""

import os
import pathlib

_TEST_DB = pathlib.Path(__file__).parent / "test_jobpulse.db"

os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["MINIMUM_REQUEST_INTERVAL_SECONDS"] = "0"
os.environ["FETCH_BASE_BACKOFF_SECONDS"] = "0.01"
os.environ["FETCH_MAX_BACKOFF_SECONDS"] = "0.05"

import httpx  # noqa: E402
import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.ingestion.fetcher import HTTPFetcher  # noqa: E402
from app.api import deps  # noqa: E402

import app.models  # noqa: E402, F401  (register all tables on Base)

from tests.fixtures.rss import DEFAULT_FEED  # noqa: E402


class RequestQueue:
    """Serves queued httpx.Response objects; falls back to a valid feed."""

    def __init__(self, default: httpx.Response | None = None) -> None:
        self.queue: list[httpx.Response] = []
        self.default = default or httpx.Response(200, text=DEFAULT_FEED)

    def enqueue(self, response: httpx.Response) -> None:
        self.queue.append(response)

    def clear(self) -> None:
        self.queue.clear()

    def handler(self, request: httpx.Request) -> httpx.Response:
        if self.queue:
            return self.queue.pop(0)
        return self.default


@pytest.fixture()
def request_queue() -> RequestQueue:
    return RequestQueue()


@pytest.fixture()
def mock_fetcher(request_queue: RequestQueue) -> HTTPFetcher:
    client = httpx.AsyncClient(transport=httpx.MockTransport(request_queue.handler))
    return HTTPFetcher(
        client=client,
        minimum_request_interval_seconds=0.0,
        base_backoff_seconds=0.01,
        max_backoff_seconds=0.05,
        max_retries=3,
    )


@pytest.fixture()
def mock_transport(request_queue: RequestQueue) -> httpx.MockTransport:
    return httpx.MockTransport(request_queue.handler)


@pytest.fixture(autouse=True)
def reset_app_db():
    """Recreate the application's SQLite tables before every test."""
    from app.db.session import engine

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session_factory():
    """Isolated in-memory DB for service-level tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    Base.metadata.drop_all(engine)


@pytest.fixture()
def client(mock_fetcher: HTTPFetcher, request_queue: RequestQueue):
    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.ingestion.service import SyncService
    from app.sources.himalayas import HimalayasRSSSource

    app = create_app()
    mock_source = HimalayasRSSSource(
        feed_url="https://example.test/rss", fetcher=mock_fetcher
    )
    app.dependency_overrides[deps.get_fetcher] = lambda: mock_fetcher
    app.dependency_overrides[deps.get_sync_service] = lambda: SyncService(
        session_factory=SessionLocal,
        source=mock_source,
        fetcher=mock_fetcher,
        settings=get_settings(),
    )
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()