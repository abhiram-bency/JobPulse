from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SyncRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int
    started_at: datetime
    completed_at: datetime | None
    status: str
    jobs_found: int
    jobs_created: int
    jobs_updated: int
    jobs_skipped: int
    jobs_invalid: int
    error_message: str | None
    duration_ms: int | None