"""Merge the calendar snapshots of several categories into one profile calendar (pure).

The category snapshots are the writer's bytes. The merge keeps them: one header and one
`VTIMEZONE` (the writer emits it only when a timed event needs it), the `VEVENT` blocks
de-duplicated by `UID` (an event can sit in a parent and a child category), sorted by start
instant and `UID`, CRLF and folding untouched. Only `X-WR-CALNAME` changes.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from itertools import takewhile
from zoneinfo import ZoneInfo

from app.modules.publicapi.ics import escape
from app.modules.publicapi.ics.fold import CRLF, fold
from app.modules.publicapi.ics.timezone import TZID
from app.modules.publicapi.ics.writer import CALENDAR_NAME, build_calendar

PROFILE_NAME = "Mein Profil"
_BERLIN = ZoneInfo(TZID)


def _physical_lines(body: bytes) -> list[str]:
    return body.decode("utf-8").split(CRLF)[:-1]


def _logical(block: Sequence[str]) -> list[str]:
    lines: list[str] = []
    for physical in block:
        if physical[:1] in (" ", "\t") and lines:
            lines[-1] += physical[1:]
        else:
            lines.append(physical)
    return lines


def _blocks(lines: Sequence[str], name: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] | None = None
    for line in lines:
        if line == f"BEGIN:{name}":
            current = []
        if current is not None:
            current.append(line)
        if line == f"END:{name}" and current is not None:
            blocks.append(current)
            current = None
    return blocks


def _line(block: Sequence[str], name: str) -> str:
    for line in _logical(block):
        if line.partition(":")[0].split(";")[0] == name:
            return line
    return ""


def _uid(block: Sequence[str]) -> str:
    return _line(block, "UID").partition(":")[2]


def _start_instant(block: Sequence[str]) -> datetime:
    head, _, value = _line(block, "DTSTART").partition(":")
    if "VALUE=DATE" in head:
        day = datetime.strptime(value, "%Y%m%d")
        return day.replace(tzinfo=_BERLIN).astimezone(UTC)
    moment = datetime.strptime(value.rstrip("Z"), "%Y%m%dT%H%M%S")
    return moment.replace(tzinfo=UTC if value.endswith("Z") else _BERLIN).astimezone(UTC)


def _header(lines: Sequence[str], title: str) -> list[str]:
    stop = ("BEGIN:VTIMEZONE", "BEGIN:VEVENT", "END:VCALENDAR")
    head = _logical(list(takewhile(lambda line: line not in stop, lines)))
    calname = f"X-WR-CALNAME:{escape.text(title)}"
    return [calname if line.startswith("X-WR-CALNAME") else line for line in head]


def merge(bodies: Sequence[bytes], name: str = PROFILE_NAME) -> bytes:
    """Return one calendar from the bodies of the category calendars.

    Args:
        bodies: Calendar files as the writer produced them.
        name: The calendar name, shown after `STUPA Events: `.
    """
    title = f"{CALENDAR_NAME}: {name}"
    if not bodies:
        return build_calendar([], base_url="", uid_domain="", name=name)
    parsed = [_physical_lines(body) for body in bodies]
    zone = next((b for lines in parsed for b in _blocks(lines, "VTIMEZONE")), None)
    events: dict[str, list[str]] = {}
    for lines in parsed:
        for block in _blocks(lines, "VEVENT"):
            events.setdefault(_uid(block), block)
    ordered = sorted(events.values(), key=lambda b: (_start_instant(b), _uid(b)))
    out = [fold(line) + CRLF for line in _header(parsed[0], title)]
    out.extend(line + CRLF for line in zone or [])
    out.extend(line + CRLF for block in ordered for line in block)
    out.append("END:VCALENDAR" + CRLF)
    return "".join(out).encode("utf-8")
