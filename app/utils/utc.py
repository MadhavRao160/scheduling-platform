"""UTC conversion at the database boundary.

The database stores naive TIMESTAMP(3) values that are always UTC.
Application code works with aware UTC datetimes. These two helpers are the
only place the conversion happens.
"""

from datetime import UTC, datetime


def to_db(value: datetime) -> datetime:
    """Aware datetime -> naive UTC, ready to store. Rejects naive input."""
    if value.tzinfo is None:
        raise ValueError("to_db expects an aware datetime")
    return value.astimezone(UTC).replace(tzinfo=None)


def from_db(value: datetime) -> datetime:
    """Naive UTC from the database -> aware UTC."""
    return value.replace(tzinfo=UTC)