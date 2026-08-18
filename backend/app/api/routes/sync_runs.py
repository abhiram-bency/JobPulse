from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.sync_run import SyncRun, SyncStatus
from app.schemas.common import Paginated
from app.schemas.sync_run import SyncRunOut

router = APIRouter(prefix="/api/v1", tags=["sync-runs"])


@router.get("/sync-runs", response_model=Paginated[SyncRunOut])
def list_sync_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    source_id: int | None = None,
    status: SyncStatus | None = None,
    db: Session = Depends(get_db),
):
    query = select(SyncRun)
    if source_id is not None:
        query = query.where(SyncRun.source_id == source_id)
    if status is not None:
        query = query.where(SyncRun.status == status)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(
        query.order_by(SyncRun.started_at.desc(), SyncRun.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return Paginated[SyncRunOut](items=rows, page=page, page_size=page_size, total=total)


@router.get("/sync-runs/{sync_id}", response_model=SyncRunOut)
def get_sync_run(sync_id: int, db: Session = Depends(get_db)):
    run = db.get(SyncRun, sync_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Sync run not found")
    return run