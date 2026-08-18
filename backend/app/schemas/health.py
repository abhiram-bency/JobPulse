from datetime import datetime

from pydantic import BaseModel

from app.schemas.source import SourceHealthOut


class SyncRequest(BaseModel):
    source_id: int | None = None


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    database: str
    timestamp: datetime
    sources: list[SourceHealthOut]