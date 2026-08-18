from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_sync_service
from app.db.session import get_db
from app.ingestion.service import SyncService, SyncSourceDisabled, SyncSourceNotFound
from app.models.source import Source
from app.schemas.health import SyncRequest
from app.schemas.sync_run import SyncRunOut

router = APIRouter(prefix="/api/v1", tags=["sync"])


@router.post("/sync", response_model=SyncRunOut)
async def create_sync(
    payload: SyncRequest | None = None,
    db: Session = Depends(get_db),
    service: SyncService = Depends(get_sync_service),
):
    if payload is not None and payload.source_id is not None:
        source_id = payload.source_id
    else:
        source_id = db.scalar(
            select(Source.id).where(Source.enabled.is_(True)).order_by(Source.id).limit(1)
        )
        if source_id is None:
            raise HTTPException(status_code=409, detail="No enabled source configured")

    try:
        run = await service.run_sync(source_id)
    except SyncSourceNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SyncSourceDisabled as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return run