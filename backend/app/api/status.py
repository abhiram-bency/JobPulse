"""Source-health computation and SourceOut assembly.

Health is derived only from measured values (last success / last failure /
staleness) — never fabricated.
"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.time import as_utc, utc_now
from app.models.job import Job
from app.models.source import Source
from app.models.sync_run import SyncRun
from app.schemas.source import SourceOut

STALE_AFTER = timedelta(hours=24)


def source_health_status(source: Source) -> str:
    """healthy | degraded | failed"""
    last_success = as_utc(source.last_success_at)
    last_failure = as_utc(source.last_failure_at)

    if last_success is None:
        return "failed"
    if last_failure is not None and last_failure > last_success:
        return "failed"
    if utc_now() - last_success > STALE_AFTER:
        return "degraded"
    return "healthy"


def build_source_out(db: Session, source: Source) -> SourceOut:
    job_count = db.scalar(
        select(func.count(Job.id)).where(Job.source_id == source.id)
    ) or 0
    last_sync = db.scalar(
        select(SyncRun)
        .where(SyncRun.source_id == source.id)
        .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .limit(1)
    )
    return SourceOut(
        id=source.id,
        name=source.name,
        type=source.type,
        base_url=source.base_url,
        enabled=source.enabled,
        last_success_at=source.last_success_at,
        last_failure_at=source.last_failure_at,
        created_at=source.created_at,
        updated_at=source.updated_at,
        health=source_health_status(source),
        job_count=job_count,
        last_sync=last_sync,
    )