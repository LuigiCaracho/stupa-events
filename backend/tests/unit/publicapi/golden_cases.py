"""The input rows of the ICS golden tests (M5 contract 8.6): view rows as `IcsRow`."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from app.modules.publicapi.ics.model import IcsRow

BERLIN = ZoneInfo("Europe/Berlin")
STAMP = datetime(2026, 10, 1, 9, 30, tzinfo=UTC)
BASE_URL = "https://events.reutlingen.university"
UID_DOMAIN = "events.reutlingen.university"


def uid(n: int) -> UUID:
    """Return a fixed event id."""
    return UUID(f"00000000-0000-4000-8000-{n:012d}")


def local(year: int, month: int, day: int, hour: int = 0, minute: int = 0) -> datetime:
    """A Berlin wall-clock time as an aware instant."""
    return datetime(year, month, day, hour, minute, tzinfo=BERLIN)


def row(n: int, title: str, starts: datetime, ends: datetime, **over: object) -> IcsRow:
    """Build a row with plain defaults; `over` replaces fields."""
    base: dict[str, object] = {
        "id": uid(n),
        "slug": f"2026-event-{n}",
        "title": title,
        "summary": None,
        "starts_at": starts,
        "ends_at": ends,
        "all_day": False,
        "starts_on": None,
        "ends_on": None,
        "tzid": "Europe/Berlin",
        "public_status": "scheduled",
        "public_seq": 1,
        "updated_at": STAMP,
        "public_reason_text": None,
        "venue_name": "Kinosaal 9-133",
        "venue_address": None,
        "venue_city": None,
        "category_slug": "kino",
        "category_name": "Kino",
        "category_parent_slug": None,
        "category_parent_name": None,
    }
    return IcsRow(**{**base, **over})  # type: ignore[arg-type]


def all_day(n: int, title: str, first: date, last: date, **over: object) -> IcsRow:
    """An all-day row from the first to the last day (inclusive)."""
    start = datetime.combine(first, datetime.min.time(), BERLIN)
    end = datetime.combine(last + timedelta(days=1), datetime.min.time(), BERLIN)
    return row(
        n, title, start, end, all_day=True, starts_on=first, ends_on=last, venue_name=None, **over
    )


def movienight() -> list[IcsRow]:
    films = (
        ("STUPA Movienight: Arrival (OmU)", local(2026, 10, 22, 20), local(2026, 10, 22, 22, 30)),
        ("Nosferatu – STUPA Movienight", local(2026, 10, 27, 20), local(2026, 10, 27, 22, 30)),
        (
            "STUPA Movienight: Halloween I (OmU)",
            local(2026, 10, 31, 20),
            local(2026, 10, 31, 23, 30),
        ),
        ("Halloween II – STUPA Movienight", local(2026, 10, 31, 23, 45), local(2026, 11, 1, 1, 30)),
        ("STUPA Movienight: Whiplash (OmU)", local(2026, 11, 9, 20), local(2026, 11, 9, 22, 30)),
        ("Das Boot – STUPA Movienight", local(2026, 11, 18, 20), local(2026, 11, 18, 22, 45)),
        ("STUPA Movienight: Stalker (OmU)", local(2026, 11, 27, 20), local(2026, 11, 27, 23, 15)),
    )
    return [
        row(n, title, start, end, summary="Der Filmabend im Kinosaal. Eintritt frei.")
        for n, (title, start, end) in enumerate(films, start=100)
    ]


def cancelled() -> list[IcsRow]:
    return [
        row(
            200,
            "Spieleabend",
            local(2026, 11, 12, 19),
            local(2026, 11, 12, 22),
            public_status="cancelled",
            public_seq=2,
            public_reason_text="Raum nicht verfügbar",
            summary="Brettspiele und Snacks.",
        )
    ]


def postponed() -> list[IcsRow]:
    return [
        row(
            210,
            "Workshop Löten",
            local(2026, 12, 3, 18),
            local(2026, 12, 3, 20),
            public_status="postponed",
            public_seq=2,
            public_reason_text="Referent erkrankt",
        ),
        row(
            211,
            "Karaoke-Abend",
            local(2026, 12, 10, 19),
            local(2026, 12, 10, 22),
            public_status="postponed",
            public_seq=3,
        ),
    ]


def all_days() -> list[IcsRow]:
    return [all_day(300, "Tag der offenen Tür", date(2026, 10, 31), date(2026, 10, 31))]


def multi_day() -> list[IcsRow]:
    return [
        row(
            400,
            "FSI LAN-Party",
            local(2026, 9, 25, 17),
            local(2026, 9, 27, 1),
            venue_name="Mensa",
            venue_address="Alteburgstraße 150",
            venue_city="Reutlingen",
        ),
        all_day(401, "Skiausfahrt Davos", date(2027, 1, 22), date(2027, 1, 24)),
    ]


def dst() -> list[IcsRow]:
    utc = lambda h, m: datetime(2026, 10, 25, h, m, tzinfo=UTC)  # noqa: E731
    return [
        row(500, "Nachtschicht", local(2026, 10, 24, 22), local(2026, 10, 25, 4)),
        row(501, "Termin 02:30 Sommerzeit", utc(0, 30), utc(0, 45)),
        row(502, "Termin 02:30 Winterzeit", utc(1, 30), utc(1, 45)),
    ]


def umlauts_fold() -> list[IcsRow]:
    return [
        row(
            600,
            "Hüttencafé – Weißbier, Äpfel; Würstchen 🎬 👩‍👩‍👧‍👦 und ein sehr langer Titel für die Faltung",
            local(2026, 11, 5, 18),
            local(2026, 11, 5, 21),
            summary="Gemütlich, mit Käse; ß ist kein B.\nZweite Zeile.",
            venue_name="Café Süd, Raum 3; Eingang links",
            venue_city="Reutlingen",
            category_name="Kino, Film",
            category_parent_name="Fachschaft",
        )
    ]


def crlf_attempt() -> list[IcsRow]:
    return [
        row(
            700,
            "Harmlos\r\nBEGIN:VALARM\r\nACTION:DISPLAY\r\nEND:VALARM\r\nURL:https://evil.example",
            local(2026, 11, 20, 19),
            local(2026, 11, 20, 21),
            summary="Zeile\rmit Trennern\x85",
            venue_name="Saal\nEND:VEVENT",
        )
    ]


CASES: dict[str, list[IcsRow]] = {
    "movienight-ws26": movienight(),
    "cancelled": cancelled(),
    "postponed": postponed(),
    "all-day": all_days(),
    "multi-day": multi_day(),
    "dst-2026-10-25": dst(),
    "umlauts-fold": umlauts_fold(),
    "crlf-attempt": crlf_attempt(),
}
