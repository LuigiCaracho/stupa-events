"""All-day events: the days are the truth, the instants follow from them (contract 2.2).

`starts_on` and `ends_on` (the last day, inclusive) are stored as dates; `starts_at` is
midnight of `starts_on` in the zone of the event and `ends_at` midnight after `ends_on`
(half-open, so days with 23 or 25 hours are right). `resolve` turns a set of column changes
into a consistent set, so `events/service` stays the only writer of these columns.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.modules.events.models import Event
from app.shared.errors import FieldError, ValidationProblem

DAY_FIELDS = frozenset({"all_day", "starts_on", "ends_on"})
TIME_FIELDS = frozenset({"starts_at", "ends_at"})


def bounds(starts_on: date, ends_on: date, tzid: str) -> tuple[datetime, datetime]:
    """Return the half-open UTC interval that covers the days `starts_on` to `ends_on`."""
    zone = ZoneInfo(tzid)
    start = datetime.combine(starts_on, time.min, zone).astimezone(UTC)
    end = datetime.combine(ends_on + timedelta(days=1), time.min, zone).astimezone(UTC)
    return start, end


def days_of(starts_at: datetime, ends_at: datetime, tzid: str) -> tuple[date, date]:
    """Return the first and last day (inclusive) that the half-open interval covers."""
    zone = ZoneInfo(tzid)
    return starts_at.astimezone(zone).date(), ends_at.astimezone(zone).date() - timedelta(days=1)


def _invalid(field: str, msg: str, code: str | None = None) -> ValidationProblem:
    return ValidationProblem(
        "Invalid request.", code=code, errors=[FieldError(field=field, msg=msg)]
    )


def resolve(event: Event, changes: dict[str, Any]) -> dict[str, Any]:
    """Return `changes` with the day and instant columns made consistent.

    Raises:
        ValidationProblem: An all-day change without `startsOn`, an end day before the start
            day, instants given for an all-day event, days given for a timed event, or a
            switch to a timed event without both instants.
    """
    if not (DAY_FIELDS & changes.keys()) and not (event.all_day and TIME_FIELDS & changes.keys()):
        return changes
    result = dict(changes)
    if result.get("all_day", event.all_day):
        if TIME_FIELDS & changes.keys():
            raise _invalid("startsAt", "the times of an all-day event follow its days")
        starts_on = changes.get("starts_on", event.starts_on)
        if starts_on is None:
            raise _invalid("startsOn", "an all-day event needs startsOn")
        keep_end = event.all_day and "starts_on" not in changes
        ends_on = changes.get("ends_on") or (event.ends_on if keep_end else None) or starts_on
        if ends_on < starts_on:
            raise _invalid("endsOn", "endsOn must not be before startsOn")
        start, end = bounds(starts_on, ends_on, event.tzid)
        result |= {
            "all_day": True,
            "starts_on": starts_on,
            "ends_on": ends_on,
            "starts_at": start,
            "ends_at": end,
            "end_estimated": False,
        }
        return result
    if {"starts_on", "ends_on"} & changes.keys():
        raise _invalid("startsOn", "days need allDay")
    if event.all_day:
        if not changes.keys() >= TIME_FIELDS:
            raise _invalid(
                "startsAt", "switching off allDay needs startsAt and endsAt", "times_required"
            )
        result |= {"all_day": False, "starts_on": None, "ends_on": None}
    return result
