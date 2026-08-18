import httpx
import pytest
from sqlalchemy import func, select

from app.ingestion.fetcher import HTTPFetcher
from app.ingestion.service import SyncService, SyncSourceDisabled, SyncSourceNotFound
from app.models.job import Job
from app.models.source import Source
from app.models.sync_run import SyncRun, SyncStatus
from app.sources.himalayas import HimalayasRSSSource

from tests.fixtures.rss import (
    DEFAULT_FEED,
    EMPTY_FEED,
    FEED_MISSING_TITLE,
    JOB_A,
    build_feed,
    item,
)


def make_service(db_factory, fetcher):
    source = HimalayasRSSSource(feed_url="https://example.test/rss", fetcher=fetcher)
    return SyncService(session_factory=db_factory, source=source, fetcher=fetcher)


def seed_source(db, *, enabled=True, name="Himalayas RSS"):
    source = Source(name=name, type="rss", base_url="https://example.test/rss", enabled=enabled)
    db.add(source)
    db.flush()
    return source.id


def job_count(db):
    return db.scalar(select(func.count(Job.id))) or 0


@pytest.mark.asyncio
async def test_successful_sync(db_session_factory, mock_fetcher):
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    run = await service.run_sync(source_id)
    assert run.status is SyncStatus.SUCCESS
    assert run.jobs_found == 2
    assert run.jobs_created == 2
    assert run.jobs_updated == 0
    assert run.jobs_skipped == 0
    assert run.jobs_invalid == 0
    assert run.error_message is None
    assert run.completed_at is not None
    assert run.duration_ms >= 0

    with db_session_factory() as db:
        source = db.get(Source, source_id)
        assert source.last_success_at is not None
        assert source.last_failure_at is None
        assert job_count(db) == 2


@pytest.mark.asyncio
async def test_partial_invalid_records(db_session_factory, mock_fetcher, request_queue):
    request_queue.clear()
    request_queue.enqueue(httpx.Response(200, text=FEED_MISSING_TITLE))
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    run = await service.run_sync(source_id)
    assert run.status is SyncStatus.SUCCESS
    assert run.jobs_found == 2
    assert run.jobs_created == 1
    assert run.jobs_invalid == 1
    # invariant: found == created + updated + skipped
    assert run.jobs_found == run.jobs_created + run.jobs_updated + run.jobs_skipped

    with db_session_factory() as db:
        assert job_count(db) == 1


@pytest.mark.asyncio
async def test_zero_result_is_suspicious(db_session_factory, mock_fetcher, request_queue):
    request_queue.clear()
    request_queue.enqueue(httpx.Response(200, text=EMPTY_FEED))
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    run = await service.run_sync(source_id)
    assert run.status is SyncStatus.SUSPICIOUS
    assert run.error_message is not None
    assert "valid" in run.error_message

    with db_session_factory() as db:
        assert job_count(db) == 0
        assert db.get(Source, source_id).last_success_at is None


@pytest.mark.asyncio
async def test_zero_result_preserves_previous_jobs(db_session_factory, mock_fetcher, request_queue):
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    first = await service.run_sync(source_id)
    assert first.status is SyncStatus.SUCCESS

    request_queue.clear()
    request_queue.enqueue(httpx.Response(200, text=EMPTY_FEED))

    second = await service.run_sync(source_id)
    assert second.status is SyncStatus.SUSPICIOUS

    with db_session_factory() as db:
        assert job_count(db) == 2  # nothing deleted


@pytest.mark.asyncio
async def test_high_invalid_ratio_is_suspicious(db_session_factory, mock_fetcher, request_queue):
    entries = [item(title="", url=f"https://example.test/broken/{i}", guid=f"b-{i}") for i in range(9)]
    entries.append(JOB_A)
    feed = build_feed(*entries)

    request_queue.clear()
    request_queue.enqueue(httpx.Response(200, text=feed))
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    run = await service.run_sync(source_id)
    assert run.status is SyncStatus.SUSPICIOUS
    assert "invalid" in run.error_message

    with db_session_factory() as db:
        assert job_count(db) == 1  # the one valid record still stored


@pytest.mark.asyncio
async def test_failed_sync_preserves_jobs(db_session_factory, mock_fetcher, request_queue):
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    first = await service.run_sync(source_id)
    assert first.status is SyncStatus.SUCCESS

    request_queue.clear()
    for _ in range(5):
        request_queue.enqueue(httpx.Response(429, text="rate limited"))

    second = await service.run_sync(source_id)
    assert second.status is SyncStatus.FAILED
    assert "429" in second.error_message
    assert second.jobs_found == 0

    with db_session_factory() as db:
        assert job_count(db) == 2  # preserved
        source = db.get(Source, source_id)
        assert source.last_failure_at is not None


@pytest.mark.asyncio
async def test_malformed_feed_marks_failed(db_session_factory, mock_fetcher, request_queue):
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    first = await service.run_sync(source_id)
    assert first.status is SyncStatus.SUCCESS

    request_queue.clear()
    from tests.fixtures.rss import MALFORMED_XML

    request_queue.enqueue(httpx.Response(200, text=MALFORMED_XML))

    second = await service.run_sync(source_id)
    assert second.status is SyncStatus.FAILED
    assert "malformed" in second.error_message.lower()

    with db_session_factory() as db:
        assert job_count(db) == 2  # preserved


@pytest.mark.asyncio
async def test_source_not_found(db_session_factory, mock_fetcher):
    service = make_service(db_session_factory, mock_fetcher)
    with pytest.raises(SyncSourceNotFound):
        await service.run_sync(999)


@pytest.mark.asyncio
async def test_disabled_source(db_session_factory, mock_fetcher):
    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db, enabled=False)
        db.commit()
    with pytest.raises(SyncSourceDisabled):
        await service.run_sync(source_id)


@pytest.mark.asyncio
async def test_concurrent_syncs_are_serialized(db_session_factory, mock_fetcher):
    import asyncio

    service = make_service(db_session_factory, mock_fetcher)
    with db_session_factory() as db:
        source_id = seed_source(db)
        db.commit()

    results = await asyncio.gather(service.run_sync(source_id), service.run_sync(source_id))
    assert all(r.status is SyncStatus.SUCCESS for r in results)
    with db_session_factory() as db:
        runs = db.scalars(select(SyncRun).where(SyncRun.source_id == source_id)).all()
        assert len(runs) == 2