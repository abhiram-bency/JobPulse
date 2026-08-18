from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.api.status import source_health_status
from app.core.config import get_settings
from app.core.time import utc_now
from app.db.session import get_db
from app.models.job import Job
from app.models.source import Source
from app.models.sync_run import SyncRun
from app.schemas.health import HealthOut
from app.schemas.source import SourceHealthOut

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)):
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "unavailable"

    sources: list[SourceHealthOut] = []
    for source in db.scalars(select(Source).order_by(Source.id)).all():
        job_count = db.scalar(
            select(func.count(Job.id)).where(Job.source_id == source.id)
        ) or 0
        last_sync = db.scalar(
            select(SyncRun)
            .where(SyncRun.source_id == source.id)
            .order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
            .limit(1)
        )
        sources.append(
            SourceHealthOut(
                id=source.id,
                name=source.name,
                type=source.type,
                base_url=source.base_url,
                enabled=source.enabled,
                health=source_health_status(source),
                job_count=job_count,
                last_success_at=source.last_success_at,
                last_failure_at=source.last_failure_at,
                last_sync=last_sync,
            )
        )

    overall = "ok" if database == "ok" else "degraded"
    return HealthOut(
        status=overall,
        app=settings.app_name,
        version=settings.app_version,
        database=database,
        timestamp=utc_now(),
        sources=sources,
    )