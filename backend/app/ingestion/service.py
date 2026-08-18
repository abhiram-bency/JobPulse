"""Sync orchestration: fetch -> parse -> validate -> normalize -> dedupe -> persist.

Also responsible for:
- sync_run lifecycle and statistics
- suspicious-result detection (empty feed, excessive invalid records)
- data preservation (we never delete jobs because of one bad sync)
- per-source in-process locking so two syncs cannot race
"""

import asyncio
import logging
import time
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ingestion.deduplicator import Deduplicator, SyncStats
from app.ingestion.fetcher import FetchError, HTTPFetcher
from app.ingestion.normalizer import utc_now
from app.ingestion.parser import ParseResult, RSSParseError
from app.ingestion.validator import JobValidator
from app.models.job import Job
from app.models.source import Source
from app.models.sync_run import SyncRun, SyncStatus
from app.sources.base import JobSource

logger = get_logger("jobpulse.ingestion.service")


class SyncSourceNotFound(Exception):
    pass


class SyncSourceDisabled(Exception):
    pass


@dataclass
class Anomaly:
    reason: str


class SyncService:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        source: JobSource,
        fetcher: HTTPFetcher,
        settings: Settings | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._source = source
        self._fetcher = fetcher
        self._settings = settings or get_settings()
        self._locks: dict[int, asyncio.Lock] = {}

    async def run_sync(self, source_id: int) -> SyncRun:
        lock = self._locks.setdefault(source_id, asyncio.Lock())
        async with lock:
            return await self._run_locked(source_id)

    # -- internals ---------------------------------------------------------------

    async def _run_locked(self, source_id: int) -> SyncRun:
        with self._session_factory() as db:
            source = db.get(Source, source_id)
            if source is None:
                raise SyncSourceNotFound(f"source {source_id} not found")
            if not source.enabled:
                raise SyncSourceDisabled(f"source {source_id} is disabled")

            run = SyncRun(source_id=source_id, status=SyncStatus.RUNNING, started_at=utc_now())
            db.add(run)
            db.commit()
            db.refresh(run)
            logger.info(
                "sync_id=%s source=%s status=started",
                run.id,
                self._source.name,
            )

            started = time.monotonic()
            try:
                fetch_result = await self._source.fetch()
                parsed = self._source.parse(fetch_result.text)
                validation = JobValidator().validate_all(parsed.items)
                normalized = [self._source.normalize(raw) for raw in validation.valid]

                anomaly = self._detect_anomaly(db, source_id, parsed, validation)
                stats = Deduplicator(db).apply(source_id, normalized, utc_now())
                stats.found = len(parsed.items)
                stats.skipped += validation.invalid_count
                stats.invalid = validation.invalid_count
                self._apply_stats(run, stats)

                if anomaly is None:
                    run.status = SyncStatus.SUCCESS
                    source.last_success_at = utc_now()
                else:
                    run.status = SyncStatus.SUSPICIOUS
                    run.error_message = anomaly.reason

                self._finish(run, started)
                db.commit()
                db.refresh(run)
            except (FetchError, RSSParseError) as exc:
                source.last_failure_at = utc_now()
                run.status = SyncStatus.FAILED
                run.error_message = str(exc)
                self._finish(run, started)
                db.commit()
                db.refresh(run)
                logger.error(
                    "sync_id=%s source=%s error=%s status=failed",
                    run.id,
                    self._source.name,
                    exc.__class__.__name__,
                )
                return run

            if run.status is SyncStatus.SUSPICIOUS:
                logger.warning(
                    "sync_id=%s source=%s reason=%s status=suspicious",
                    run.id,
                    self._source.name,
                    run.error_message,
                )
            else:
                logger.info(
                    "sync_id=%s jobs_found=%d jobs_created=%d jobs_updated=%d "
                    "jobs_skipped=%d jobs_invalid=%d duration_ms=%d status=%s",
                    run.id,
                    run.jobs_found,
                    run.jobs_created,
                    run.jobs_updated,
                    run.jobs_skipped,
                    run.jobs_invalid,
                    run.duration_ms,
                    run.status.value,
                )
            return run

    def _apply_stats(self, run: SyncRun, stats: SyncStats) -> None:
        run.jobs_found = stats.found
        run.jobs_created = stats.created
        run.jobs_updated = stats.updated
        run.jobs_skipped = stats.skipped
        run.jobs_invalid = stats.invalid

    def _finish(self, run: SyncRun, started: float) -> None:
        run.completed_at = utc_now()
        run.duration_ms = int((time.monotonic() - started) * 1000)

    def _detect_anomaly(
        self, db: Session, source_id: int, parsed: ParseResult, validation
    ) -> Anomaly | None:
        valid_count = len(validation.valid)
        total_entries = len(parsed.items)
        invalid_count = validation.invalid_count

        if valid_count == 0:
            previous_jobs = db.scalar(
                select(func.count(Job.id)).where(Job.source_id == source_id)
            )
            hint = (
                f"previous data preserved ({previous_jobs} jobs kept)"
                if previous_jobs
                else "no jobs in database yet"
            )
            return Anomaly(
                f"feed returned {total_entries} entries but {valid_count} valid; "
                f"{hint}"
            )

        if total_entries >= self._settings.anomaly_min_total_entries:
            invalid_ratio = invalid_count / total_entries
            if invalid_ratio > self._settings.max_invalid_ratio:
                return Anomaly(
                    f"{invalid_count}/{total_entries} records invalid "
                    f"({invalid_ratio:.0%}); schema may have changed"
                )
        return None