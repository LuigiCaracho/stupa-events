"""Time helpers: aware UTC now, strict awareness checks and local-zone conversion.

Every timestamp in the platform is timezone-aware. The wire format is UTC; an event
keeps its own `tzid` (always `Europe/Berlin` in v1) for display and for the calendar
day it belongs to.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

DEFAULT_TZID = "Europe/Berlin"


def utcnow() -> datetime:
    """Return the current time as an aware UTC datetime."""
    return datetime.now(UTC)


def require_aware(value: datetime) -> datetime:
    """Return `value` unchanged when it is timezone-aware.

    Raises:
        ValueError: The datetime is naive.
    """
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("naive datetime: a timezone offset is required")
    return value


def to_utc(value: datetime) -> datetime:
    """Convert an aware datetime to UTC.

    Raises:
        ValueError: The datetime is naive.
    """
    return require_aware(value).astimezone(UTC)


def to_local(value: datetime, tzid: str = DEFAULT_TZID) -> datetime:
    """Convert an aware datetime to the wall-clock time of `tzid`.

    Raises:
        ValueError: The datetime is naive.
        zoneinfo.ZoneInfoNotFoundError: `tzid` is unknown.
    """
    return require_aware(value).astimezone(ZoneInfo(tzid))


def local_date_iso(value: datetime, tzid: str = DEFAULT_TZID) -> str:
    """Return the local calendar day of `value` as `YYYY-MM-DD` (used in event slugs)."""
    return to_local(value, tzid).date().isoformat()
