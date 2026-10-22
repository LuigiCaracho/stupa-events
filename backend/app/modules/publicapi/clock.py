"""The clock of the public routes: an injectable `now` and the Berlin day boundaries.

Days on the public site are Berlin calendar days, never the server's zone. A test replaces
`now` through `app.dependency_overrides`.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends

BERLIN = ZoneInfo("Europe/Berlin")


def now() -> datetime:
    """Return the current instant as aware UTC."""
    return datetime.now(UTC)


Now = Annotated[datetime, Depends(now)]


def berlin_date(moment: datetime) -> date:
    """Return the Berlin calendar day of an instant."""
    return moment.astimezone(BERLIN).date()


def day_start(day: date) -> datetime:
    """Return the instant (UTC) at which a Berlin day begins."""
    return datetime.combine(day, time.min, BERLIN).astimezone(UTC)


def day_end(day: date) -> datetime:
    """Return the instant (UTC) at which the next Berlin day begins (exclusive end)."""
    return day_start(day + timedelta(days=1))


def month_bounds(year: int, month: int) -> tuple[datetime, datetime]:
    """Return the first instant of a Berlin month and of the following one."""
    first = date(year, month, 1)
    following = date(year + (month == 12), month % 12 + 1, 1)
    return day_start(first), day_start(following)


def months_between(moment: datetime, year: int, month: int) -> int:
    """Return how many months `year-month` lies after the Berlin month of `moment`."""
    today = berlin_date(moment)
    return (year - today.year) * 12 + month - today.month
