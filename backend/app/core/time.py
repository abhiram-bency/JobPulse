"""UTC time helpers.

All application timestamps are UTC. Values are stored as naive-UTC in SQLite
(used by tests) and as tz-aware UTC by Postgres; ``as_utc`` normalizes either
representation so comparisons are safe.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Naive UTC datetime, suitable for both SQLite and Postgres columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)