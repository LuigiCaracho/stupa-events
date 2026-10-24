"""Profile calendar merge: de-duplication by UID, one VTIMEZONE, stable order, writer bytes."""

from __future__ import annotations

from datetime import date

from icalendar import Calendar

from app.modules.publicapi.ics.fold import CRLF
from app.modules.publicapi.ics.writer import build_calendar
from app.modules.subscriptions.ics_merge import merge
from tests.unit.publicapi.golden_cases import BASE_URL, UID_DOMAIN, all_day, local, row


def calendar(*rows) -> bytes:  # noqa: ANN002, ANN201
    return build_calendar(list(rows), base_url=BASE_URL, uid_domain=UID_DOMAIN)


PARTY = row(1, "Party", local(2026, 11, 7, 22), local(2026, 11, 8, 3))
FILM = row(2, "Film", local(2026, 11, 2, 20), local(2026, 11, 2, 22))
LONG = row(
    3, "Ö" * 60 + " sehr langer Titel mit Umlauten", local(2026, 11, 9, 9), local(2026, 11, 9, 10)
)
FAIR = all_day(4, "Messe", date(2026, 11, 5), date(2026, 11, 6))
CHANGE = row(5, "Zeitumstellung", local(2026, 10, 25, 2, 30), local(2026, 10, 25, 3, 30))


def uids(body: bytes) -> list[str]:
    return [str(e["UID"]).split("@")[0][-3:] for e in Calendar.from_ical(body).walk("VEVENT")]


def test_events_of_two_calendars_are_sorted_by_start() -> None:
    merged = merge([calendar(PARTY, LONG), calendar(FILM, FAIR)])
    assert uids(merged) == ["002", "004", "001", "003"]


def test_an_event_in_parent_and_child_appears_once() -> None:
    merged = merge([calendar(PARTY, FILM), calendar(PARTY)])
    assert uids(merged).count("001") == 1 and len(uids(merged)) == 2


def test_a_single_vtimezone_survives_and_only_when_needed() -> None:
    merged = merge([calendar(PARTY), calendar(FILM)])
    assert merged.count(b"BEGIN:VTIMEZONE") == 1
    assert merge([calendar(FAIR), calendar(FAIR)]).count(b"BEGIN:VTIMEZONE") == 0


def test_the_header_names_the_profile_and_the_rest_is_the_writer_text() -> None:
    merged = merge([calendar(PARTY)]).decode()
    assert "X-WR-CALNAME:STUPA Events: Mein Profil\r\n" in merged
    assert merged.startswith("BEGIN:VCALENDAR\r\nVERSION:2.0\r\n")
    assert merged.endswith("END:VCALENDAR\r\n")
    single = (
        calendar(PARTY)
        .decode()
        .replace("X-WR-CALNAME:STUPA Events\r\n", "X-WR-CALNAME:STUPA Events: Mein Profil\r\n")
    )
    assert merged == single


def test_folding_and_crlf_stay_intact() -> None:
    merged = merge([calendar(LONG, PARTY), calendar(FILM)])
    assert b"\n" not in merged.replace(b"\r\n", b"")
    assert all(len(line.encode()) <= 75 for line in merged.decode().split(CRLF)[:-1])
    summaries = [str(e["SUMMARY"]) for e in Calendar.from_ical(merged).walk("VEVENT")]
    assert LONG.title in summaries


def test_the_order_does_not_depend_on_the_input_order() -> None:
    a, b = calendar(PARTY, LONG), calendar(FILM, FAIR, CHANGE)
    assert merge([a, b]) == merge([b, a])


def test_the_merge_is_deterministic_and_empty_input_gives_an_empty_calendar() -> None:
    assert merge([calendar(PARTY)]) == merge([calendar(PARTY)])
    empty = Calendar.from_ical(merge([]))
    assert list(empty.walk("VEVENT")) == []
    assert str(empty["X-WR-CALNAME"]) == "STUPA Events: Mein Profil"
