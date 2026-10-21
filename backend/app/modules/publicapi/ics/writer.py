"""The iCalendar writer: fixed property order, CRLF, folding, `TZID` with a `VTIMEZONE` block.

Deterministic bytes, no runtime dependency: the same rows give the same file, so the golden
tests compare byte for byte. Timed events are written in local time with `TZID=Europe/Berlin`
(both passes of the repeated hour of the October change in UTC), all-day events as `DATE`.
`DTSTAMP` and `LAST-MODIFIED` are the last change of the event, not the build time. Never
written: `ORGANIZER`, `ATTENDEE`, `VALARM`, `GEO`, `ATTACH`, the long description, any
`X-` property except `X-WR-*` and `X-PUBLISHED-TTL`.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/calendar/ics.py (rewritten: TZID)
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from app.modules.publicapi.ics import escape
from app.modules.publicapi.ics.fold import CRLF, fold
from app.modules.publicapi.ics.model import IcsRow
from app.modules.publicapi.ics.timezone import TZID, VTIMEZONE, ambiguous_instant, local

PRODID = "-//STUPA Events//Kalender//DE"
CALENDAR_NAME = "STUPA Events"
STATUS = {"scheduled": "CONFIRMED", "cancelled": "CANCELLED", "postponed": "TENTATIVE"}
REASON_LABEL = {"cancelled": "Abgesagt", "postponed": "Verschoben"}
_STAMP = "%Y%m%dT%H%M%SZ"
_LOCAL = "%Y%m%dT%H%M%S"


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime(_STAMP)


def _instant(name: str, value: datetime, tzid: str) -> tuple[str, bool]:
    """Return the property line of a timed instant and whether it uses `TZID`."""
    if ambiguous_instant(value, tzid):
        return f"{name}:{_utc(value)}", False
    return f"{name};TZID={tzid}:{local(value, tzid).strftime(_LOCAL)}", True


def _description(row: IcsRow) -> str | None:
    lines: list[str] = []
    label = REASON_LABEL.get(row.public_status)
    if label:
        lines.append(f"{label}: {row.public_reason_text}" if row.public_reason_text else label)
    if row.summary:
        lines.append(row.summary)
    return escape.lines(lines) if lines else None


def _location(row: IcsRow) -> str | None:
    if row.venue_name is None:
        return None
    return escape.text(
        ", ".join(p for p in (row.venue_name, row.venue_address, row.venue_city) if p)
    )


def _categories(row: IcsRow) -> str | None:
    names = [n for n in (row.category_name, row.category_parent_name) if n]
    return ",".join(escape.text(n) for n in names) or None


def _dates(row: IcsRow) -> tuple[list[str], bool]:
    if row.all_day:
        assert row.starts_on is not None and row.ends_on is not None
        end = row.ends_on + timedelta(days=1)
        return [
            f"DTSTART;VALUE=DATE:{row.starts_on:%Y%m%d}",
            f"DTEND;VALUE=DATE:{end:%Y%m%d}",
        ], False
    start, start_zoned = _instant("DTSTART", row.starts_at, row.tzid)
    end, end_zoned = _instant("DTEND", row.ends_at, row.tzid)
    return [start, end], start_zoned or end_zoned


def event_lines(row: IcsRow, base_url: str, uid_domain: str) -> tuple[list[str], bool]:
    """Return the property lines of one VEVENT in the fixed order, and whether it uses `TZID`."""
    dates, zoned = _dates(row)
    stamp = _utc(row.updated_at)
    optional = (
        ("DESCRIPTION", _description(row)),
        ("LOCATION", _location(row)),
        ("CATEGORIES", _categories(row)),
    )
    lines = [
        f"UID:{row.id}@{uid_domain}",
        f"DTSTAMP:{stamp}",
        f"LAST-MODIFIED:{stamp}",
        f"SEQUENCE:{row.public_seq}",
        f"SUMMARY:{escape.text(row.title)}",
        *dates,
        f"STATUS:{STATUS[row.public_status]}",
        *(f"{name}:{value}" for name, value in optional if value),
        f"URL:{base_url}/e/{row.slug}",
    ]
    return lines, zoned


def build_calendar(
    rows: Sequence[IcsRow], *, base_url: str, uid_domain: str, name: str | None = None
) -> bytes:
    """Render the rows into a `VCALENDAR` (bytes, CRLF, UTF-8).

    Args:
        rows: The events, already filtered and sorted.
        base_url: The public site, for the event `URL`.
        uid_domain: The domain behind the stable `UID` (`<event id>@<domain>`).
        name: The calendar name for a category calendar ("STUPA Events: <name>").
    """
    events = [event_lines(row, base_url.rstrip("/"), uid_domain) for row in rows]
    title = f"{CALENDAR_NAME}: {name}" if name else CALENDAR_NAME
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{PRODID}",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape.text(title)}",
        f"X-WR-TIMEZONE:{TZID}",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
        "X-PUBLISHED-TTL:PT1H",
    ]
    if any(zoned for _, zoned in events):
        lines.extend(VTIMEZONE)
    for body, _ in events:
        lines.extend(["BEGIN:VEVENT", *body, "END:VEVENT"])
    lines.append("END:VCALENDAR")
    return "".join(fold(line) + CRLF for line in lines).encode()
