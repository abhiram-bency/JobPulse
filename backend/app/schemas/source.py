from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.sync_run import SyncRunOut


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    type: str
    base_url: str
    enabled: bool
    last_success_at: datetime | None
    last_failure_at: datetime | None
    created_at: datetime
    updated_at: datetime
    health: str
    job_count: int
    last_sync: SyncRunOut | None


class SourceHealthOut(BaseModel):
    id: int
    name: str
    type: str
    base_url: str
    enabled: bool
    health: str
    job_count: int
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_sync: SyncRunOut | None