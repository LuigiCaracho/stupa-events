"""Map view rows to the writer's input, and pick the rows of one calendar (contract 8.1)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Row

from app.modules.publicapi.ics.model import IcsRow
from app.modules.publicapi.ics.timezone import TZID

PAST_MONTHS_DAYS = 92
FUTURE_DAYS = 366


def ics_row(row: Row[Any]) -> IcsRow:
    """Copy exactly the allowlisted fields of a view row; nothing else crosses over.

    The writer emits only the `VTIMEZONE` of `TZID`, so the instants are always written in
    that zone, whatever zone the column holds.
    """
    return IcsRow(
        id=row.id,
        slug=row.slug,
        title=row.title,
        summary=row.summary,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        all_day=row.all_day,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        tzid=TZID,
        public_status=row.public_status,
        public_seq=row.public_seq,
        updated_at=row.updated_at,
        public_reason_text=row.public_reason_text,
        venue_name=row.venue_name,
        venue_address=row.venue_address,
        venue_city=row.venue_city,
        category_slug=row.category_slug,
        category_name=row.category_name,
        category_parent_slug=row.category_parent_slug,
        category_parent_name=row.category_parent_name,
    )


def window_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Return the instants that bound a calendar: three months back, twelve months ahead."""
    return now - timedelta(days=PAST_MONTHS_DAYS), now + timedelta(days=FUTURE_DAYS)


def in_window(row: IcsRow, now: datetime) -> bool:
    """Tell if an event ends within the last three months or starts within twelve months."""
    first, last = window_bounds(now)
    return row.ends_at >= first and row.starts_at <= last


def windowed(rows: Sequence[IcsRow], now: datetime) -> list[IcsRow]:
    """Keep the rows inside the window, sorted by start and id."""
    return sorted((r for r in rows if in_window(r, now)), key=lambda r: (r.starts_at, str(r.id)))
