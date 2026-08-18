import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SyncStatus(str, enum.Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SUSPICIOUS = "suspicious"


class SyncRun(Base):
    __tablename__ = "sync_runs"
    __table_args__ = (Index("ix_sync_runs_started_at", "started_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[SyncStatus] = mapped_column(
        Enum(
            SyncStatus,
            name="sync_status",
            native_enum=False,
            values_callable=lambda enum: [member.value for member in enum],
        ),
        default=SyncStatus.RUNNING,
        nullable=False,
    )
    jobs_found: Mapped[int] = mapped_column(default=0, nullable=False)
    jobs_created: Mapped[int] = mapped_column(default=0, nullable=False)
    jobs_updated: Mapped[int] = mapped_column(default=0, nullable=False)
    jobs_skipped: Mapped[int] = mapped_column(default=0, nullable=False)
    jobs_invalid: Mapped[int] = mapped_column(default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(nullable=True)

    source: Mapped["Source"] = relationship(back_populates="sync_runs")