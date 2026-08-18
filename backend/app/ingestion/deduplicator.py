"""Database-level deduplication and upsert of normalized jobs.

Uniqueness is enforced in two layers:
1. The ``UNIQUE(source_id, external_id)`` database constraint.
2. This module, which first checks what already exists and decides
   created / updated / skipped per job.

Existing jobs are never deleted by a sync, so stale data always survives
temporary source failures.
"""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.normalizer import NormalizedJob
from app.models.job import Job

_MUTABLE_FIELDS = ("title", "company", "location", "description", "url", "published_at")


@dataclass
class SyncStats:
    found: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0
    invalid: int = 0


class Deduplicator:
    def __init__(self, session: Session) -> None:
        self._session = session

    def apply(self, source_id: int, jobs: list[NormalizedJob], now: datetime) -> SyncStats:
        stats = SyncStats()
        if not jobs:
            return stats

        existing = self._load_existing(source_id, jobs)
        seen: set[str] = set()

        for job in jobs:
            if job.external_id in seen:
                stats.skipped += 1
                continue
            seen.add(job.external_id)

            row = existing.get(job.external_id)
            if row is None:
                self._create(source_id, job, now)
                stats.created += 1
            elif self._differs(row, job):
                self._update(row, job, now)
                stats.updated += 1
            else:
                row.last_seen_at = now
                stats.skipped += 1

        self._session.flush()
        return stats

    # -- internals --------------------------------------------------------------

    def _load_existing(self, source_id: int, jobs: list[NormalizedJob]) -> dict[str, Job]:
        external_ids = [job.external_id for job in jobs]
        rows = self._session.scalars(
            select(Job).where(Job.source_id == source_id, Job.external_id.in_(external_ids))
        ).all()
        return {row.external_id: row for row in rows}

    @staticmethod
    def _differs(row: Job, job: NormalizedJob) -> bool:
        return any(getattr(row, field) != getattr(job, field) for field in _MUTABLE_FIELDS)

    def _create(self, source_id: int, job: NormalizedJob, now: datetime) -> None:
        self._session.add(
            Job(
                source_id=source_id,
                external_id=job.external_id,
                title=job.title,
                company=job.company,
                location=job.location,
                description=job.description,
                url=job.url,
                published_at=job.published_at,
                first_seen_at=now,
                last_seen_at=now,
            )
        )

    def _update(self, row: Job, job: NormalizedJob, now: datetime) -> None:
        for field in _MUTABLE_FIELDS:
            setattr(row, field, getattr(job, field))
        row.last_seen_at = now