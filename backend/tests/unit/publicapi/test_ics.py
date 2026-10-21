"""ICS writer: goldens, folding, escaping, injection, the VTIMEZONE block, determinism."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from icalendar import Calendar

from app.modules.publicapi.ics import escape
from app.modules.publicapi.ics.fold import CRLF, fold
from app.modules.publicapi.ics.timezone import VTIMEZONE, ambiguous_instant
from app.modules.publicapi.ics.writer import build_calendar
from tests.unit.publicapi.golden_cases import BASE_URL, CASES, UID_DOMAIN, local, row

GOLDEN = Path(__file__).resolve().parents[2] / "golden" / "ics"


def render(name: str) -> bytes:
    return build_calendar(CASES[name], base_url=BASE_URL, uid_domain=UID_DOMAIN)


@pytest.mark.parametrize("name", sorted(CASES))
def test_ics_goldens(name: str) -> None:
    path = GOLDEN / f"{name}.ics"
    body = render(name)
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_bytes(body)
    assert body == path.read_bytes()


def unfold(body: bytes) -> list[str]:
    return body.decode().replace("\r\n ", "").split("\r\n")[:-1]


@pytest.mark.parametrize("name", sorted(CASES))
def test_ics_parses_with_icalendar(name: str) -> None:
    calendar = Calendar.from_ical(render(name))
    events = list(calendar.walk("VEVENT"))
    assert len(events) == len(CASES[name])
    uids = [str(e["UID"]) for e in events]
    assert len(uids) == len(set(uids))
    for event in events:
        assert event["DTEND"].dt >= event["DTSTART"].dt  # type: ignore[operator]
        assert not list(event.walk("VALARM"))
    assert str(calendar["PRODID"]) == "-//STUPA Events//Kalender//DE"


@pytest.mark.parametrize("name", sorted(CASES))
def test_ics_unfold_roundtrip(name: str) -> None:
    body = render(name)
    assert body.endswith(CRLF.encode()) and b"\n" not in body.replace(b"\r\n", b"")
    for physical in body.decode().split(CRLF)[:-1]:
        assert len(physical.encode()) <= 75
    assert all(line.count("\r") == 0 for line in unfold(body))


def test_ics_order_is_deterministic() -> None:
    assert render("movienight-ws26") == render("movienight-ws26")
    lines = unfold(render("cancelled"))
    names = [line.split(":", 1)[0].split(";", 1)[0] for line in lines]
    assert names[names.index("UID") : names.index("URL") + 1] == [
        "UID",
        "DTSTAMP",
        "LAST-MODIFIED",
        "SEQUENCE",
        "SUMMARY",
        "DTSTART",
        "DTEND",
        "STATUS",
        "DESCRIPTION",
        "LOCATION",
        "CATEGORIES",
        "URL",
    ]


def test_ics_uid_domain_is_pinned() -> None:
    from app.settings import Settings

    assert Settings.model_fields["ics_uid_domain"].default == "events.reutlingen.university"
    lines = unfold(render("cancelled"))
    assert "UID:00000000-0000-4000-8000-000000000200@events.reutlingen.university" in lines


def test_the_status_sequence_and_reason_of_a_cancellation() -> None:
    lines = unfold(render("cancelled"))
    assert "STATUS:CANCELLED" in lines and "SEQUENCE:2" in lines
    assert "DESCRIPTION:Abgesagt: Raum nicht verfügbar\\nBrettspiele und Snacks." in lines
    postponed = unfold(render("postponed"))
    assert postponed.count("STATUS:TENTATIVE") == 2
    assert "DESCRIPTION:Verschoben: Referent erkrankt" in postponed
    assert "DESCRIPTION:Verschoben" in postponed


def test_all_day_events_use_value_date_with_an_exclusive_end() -> None:
    lines = unfold(render("all-day"))
    assert "DTSTART;VALUE=DATE:20261031" in lines and "DTEND;VALUE=DATE:20261101" in lines
    assert "BEGIN:VTIMEZONE" not in lines
    multi = unfold(render("multi-day"))
    assert "DTSTART;VALUE=DATE:20270122" in multi and "DTEND;VALUE=DATE:20270125" in multi
    assert "DTSTART;TZID=Europe/Berlin:20260925T170000" in multi
    assert "DTEND;TZID=Europe/Berlin:20260927T010000" in multi


def test_the_repeated_hour_of_the_october_change_is_written_in_utc() -> None:
    lines = unfold(render("dst-2026-10-25"))
    assert "DTSTART:20261025T003000Z" in lines
    assert "DTSTART:20261025T013000Z" in lines
    assert "DTEND;TZID=Europe/Berlin:20261025T040000" in lines
    assert ambiguous_instant(datetime(2026, 10, 25, 1, 30, tzinfo=UTC))
    assert ambiguous_instant(datetime(2026, 10, 25, 0, 30, tzinfo=UTC))
    assert not ambiguous_instant(datetime(2026, 10, 25, 2, 0, tzinfo=UTC))
    assert not ambiguous_instant(datetime(2026, 10, 24, 23, 59, tzinfo=UTC))
    assert not ambiguous_instant(datetime(2026, 3, 29, 1, 30, tzinfo=UTC))


def test_a_hostile_row_yields_one_event_and_clean_text() -> None:
    body = render("crlf-attempt")
    lines = unfold(body)
    assert body.count(b"BEGIN:VEVENT") == 1
    assert "BEGIN:VALARM" not in lines and "END:VEVENT" in lines
    assert [line for line in lines if line.startswith("URL:")] == [
        f"URL:{BASE_URL}/e/2026-event-700"
    ]


def test_the_calendar_header_and_name() -> None:
    plain = unfold(build_calendar([], base_url=BASE_URL, uid_domain=UID_DOMAIN))
    assert plain[:4] == [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//STUPA Events//Kalender//DE",
        "CALSCALE:GREGORIAN",
    ]
    assert "X-WR-CALNAME:STUPA Events" in plain and "BEGIN:VTIMEZONE" not in plain
    named = unfold(
        build_calendar([], base_url=BASE_URL + "/", uid_domain=UID_DOMAIN, name="Kino, Film")
    )
    assert "X-WR-CALNAME:STUPA Events: Kino\\, Film" in named
    assert "REFRESH-INTERVAL;VALUE=DURATION:PT1H" in named and "X-PUBLISHED-TTL:PT1H" in named
    assert named[-1] == "END:VCALENDAR"


def test_ics_fold() -> None:
    short = "SUMMARY:kurz"
    assert fold(short) == short
    long = "SUMMARY:" + "ü" * 100
    folded = fold(long).split(CRLF)
    assert all(len(p.encode()) <= 75 for p in folded) and all(p.startswith(" ") for p in folded[1:])
    assert "".join([folded[0], *(p[1:] for p in folded[1:])]) == long
    zwj = "SUMMARY:" + "👩‍👩‍👧‍👦" * 6
    assert "".join(p.lstrip(" ") if i else p for i, p in enumerate(fold(zwj).split(CRLF))) == zwj


def test_ics_escape() -> None:
    assert escape.text("a,b;c\\d") == "a\\,b\\;c\\\\d"
    assert escape.text("zeile\r\nzwei\x00 drei\x85") == "zeile  zwei  drei "
    assert escape.lines(["eins, zwei", "drei\nvier"]) == "eins\\, zwei\\ndrei vier"
    assert escape.clean("\t") == " "


@settings(max_examples=200, deadline=None)
@given(st.text())
def test_ics_text_never_injects(value: str) -> None:
    body = build_calendar(
        [
            row(
                1,
                value or "x",
                local(2026, 11, 5, 19),
                local(2026, 11, 5, 21),
                summary=value,
                venue_name=value or None,
                category_name=value or None,
            )
        ],
        base_url=BASE_URL,
        uid_domain=UID_DOMAIN,
    )
    calendar = Calendar.from_ical(body)
    events = list(calendar.walk("VEVENT"))
    assert len(events) == 1 and not list(events[0].walk("VALARM"))
    assert str(events[0]["URL"]) == f"{BASE_URL}/e/2026-event-1"
    assert body.count(b"BEGIN:VEVENT") == 1


def test_vtimezone_matches_zoneinfo() -> None:
    rules = {
        "DAYLIGHT": (3, "+0200", "+0100"),
        "STANDARD": (10, "+0100", "+0200"),
    }
    assert "RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=-1SU" in VTIMEZONE
    assert "RRULE:FREQ=YEARLY;BYMONTH=10;BYDAY=-1SU" in VTIMEZONE
    assert rules and "TZOFFSETTO:+0200" in VTIMEZONE and "TZOFFSETTO:+0100" in VTIMEZONE
    zone = ZoneInfo("Europe/Berlin")

    def zone_offset(instant: datetime) -> timedelta:
        offset = instant.astimezone(zone).utcoffset()
        assert offset is not None
        return offset

    def last_sunday(year: int, month: int) -> datetime:
        day = datetime(year, month + 1 if month < 12 else 1, 1, tzinfo=UTC) - timedelta(days=1)
        while day.weekday() != 6:
            day -= timedelta(days=1)
        return day.replace(tzinfo=None)

    def offset_by_rules(instant: datetime) -> int:
        spring = last_sunday(instant.year, 3).replace(hour=1)
        autumn = last_sunday(instant.year, 10).replace(hour=1)
        naive = instant.replace(tzinfo=None)
        return 2 if spring <= naive < autumn else 1

    moment = datetime(2025, 1, 1, tzinfo=UTC)
    while moment.year < 2031:
        assert int(zone_offset(moment).total_seconds() // 3600) == offset_by_rules(moment), moment
        moment += timedelta(hours=1)


def test_foreign_tzid_is_written_in_the_one_zone_that_has_a_vtimezone() -> None:
    from dataclasses import asdict
    from types import SimpleNamespace

    from app.modules.publicapi.ics.rows import ics_row

    source = row(1, "Fremd", local(2026, 6, 1, 19), local(2026, 6, 1, 21), tzid="Asia/Tokyo")
    mapped = ics_row(SimpleNamespace(**asdict(source)))  # type: ignore[arg-type]
    body = build_calendar([mapped], base_url=BASE_URL, uid_domain=UID_DOMAIN).decode()
    assert "Asia/Tokyo" not in body
    assert "DTSTART;TZID=Europe/Berlin:20260601T190000" in body
