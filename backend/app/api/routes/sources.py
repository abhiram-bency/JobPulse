from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.status import build_source_out
from app.db.session import get_db
from app.models.source import Source
from app.schemas.source import SourceOut

router = APIRouter(prefix="/api/v1", tags=["sources"])


@router.get("/sources", response_model=list[SourceOut])
def list_sources(db: Session = Depends(get_db)):
    sources = db.scalars(select(Source).order_by(Source.id)).all()
    return [build_source_out(db, source) for source in sources]


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: int, db: Session = Depends(get_db)):
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return build_source_out(db, source)