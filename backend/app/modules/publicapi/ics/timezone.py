"""`VTIMEZONE` Europe/Berlin and the rule for the repeated hour (contract 8.2, 8.3).

The block carries the two EU rules since 1996: summer time starts on the last Sunday of
March at 02:00 local time, ends on the last Sunday of October at 03:00. `ambiguous_instant`
finds the instants that fall into the repeated hour of the October change, on either pass:
a local time with `TZID` is ambiguous there, so the writer emits them in UTC (decision D8,
widened in the M5 integration: ical.js, the parser of Thunderbird, reads an ambiguous
`TZID` time as the second pass, so the first pass needs UTC as much as the second).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TZID = "Europe/Berlin"
VTIMEZONE = (
    "BEGIN:VTIMEZONE",
    f"TZID:{TZID}",
    f"X-LIC-LOCATION:{TZID}",
    "BEGIN:DAYLIGHT",
    "TZOFFSETFROM:+0100",
    "TZOFFSETTO:+0200",
    "TZNAME:CEST",
    "DTSTART:19700329T020000",
    "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU",
    "END:DAYLIGHT",
    "BEGIN:STANDARD",
    "TZOFFSETFROM:+0200",
    "TZOFFSETTO:+0100",
    "TZNAME:CET",
    "DTSTART:19701025T030000",
    "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU",
    "END:STANDARD",
    "END:VTIMEZONE",
)


def local(instant: datetime, tzid: str = TZID) -> datetime:
    """Return the wall-clock time of an aware instant in `tzid` (with `fold` set)."""
    return instant.astimezone(ZoneInfo(tzid))


def ambiguous_instant(instant: datetime, tzid: str = TZID) -> bool:
    """Tell if the wall-clock time of the instant occurs twice (the repeated local hour)."""
    wall = local(instant, tzid)
    return wall.replace(fold=1 - wall.fold).utcoffset() != wall.utcoffset()
