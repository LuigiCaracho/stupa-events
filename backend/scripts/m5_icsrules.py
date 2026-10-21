"""RFC 5545 rules for a published calendar, in the spirit of an iCalendar validator.

Thunderbird is not run here (too heavy for the dev machine); these rules cover what the
clients choke on: CRLF line ends, folding at 75 octets, the required properties of the
calendar and of every event, unique UIDs, a `VTIMEZONE` for every `TZID`, an end after the
start, no control characters and no property the public calendar must never carry.
"""

from __future__ import annotations

import re

from icalendar import Calendar

FORBIDDEN = ("ORGANIZER", "ATTENDEE", "VALARM", "ATTACH", "GEO")
REQUIRED_EVENT = ("UID", "DTSTAMP", "DTSTART", "SUMMARY")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_TZID = re.compile(r";TZID=([^:;]+)")


def _line_problems(body: bytes) -> list[str]:
    found: list[str] = []
    if not body.endswith(b"\r\n"):
        found.append("no CRLF at the end")
    lines = body.split(b"\r\n")[:-1]
    if any(b"\n" in line or b"\r" in line for line in lines):
        found.append("bare LF or CR")
    found += [
        f"line {n} has {len(line)} octets" for n, line in enumerate(lines, 1) if len(line) > 75
    ]
    text = body.decode("utf-8")
    if _CONTROL.search(text.replace("\r\n", "")):
        found.append("control character")
    unfolded = text.replace("\r\n ", "").splitlines()
    names = {line.split(":", 1)[0].split(";", 1)[0] for line in unfolded}
    found += [
        f"forbidden {name}" for name in FORBIDDEN if name in names or f"BEGIN:{name}" in unfolded
    ]
    zones = {m.group(1) for line in unfolded for m in _TZID.finditer(line)}
    defined = {line.split(":", 1)[1] for line in unfolded if line.startswith("TZID:")}
    found += [f"TZID {zone} without VTIMEZONE" for zone in sorted(zones - defined)]
    return found


def problems(body: bytes) -> list[str]:
    """Return every rule the calendar `body` breaks (empty when it is clean)."""
    found = _line_problems(body)
    calendar = Calendar.from_ical(body)
    for name in ("VERSION", "PRODID"):
        if name not in calendar:
            found.append(f"calendar without {name}")
    uids: set[str] = set()
    for event in calendar.walk("VEVENT"):
        found += [f"event without {n}" for n in REQUIRED_EVENT if n not in event]
        uid = str(event.get("UID"))
        if uid in uids:
            found.append(f"duplicate UID {uid}")
        uids.add(uid)
        start, end = event.get("DTSTART"), event.get("DTEND")
        if start is not None and end is not None and not end.dt > start.dt:
            found.append(f"{uid}: DTEND not after DTSTART")
        if str(event.get("STATUS", "CONFIRMED")) not in {"CONFIRMED", "CANCELLED", "TENTATIVE"}:
            found.append(f"{uid}: unknown STATUS")
    return found
