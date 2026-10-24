"""What the HTML shell says about a page: title, description, image, links and noscript list.

`Page` is the finished description; `page.py` turns it into markup. German date text is built
by hand (no locale of the server is used), always in Berlin time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import Row

from app.modules.publicapi.clock import BERLIN
from app.modules.publicapi.query.cards import image_set
from app.modules.publicapi.shell.jsonld import event_data, serialize
from app.modules.publicapi.site_schemas import PublicEventCard

SITE = "STUPA Events"
DEFAULT_IMAGE = "/og-default.png"
DEFAULT_ALT = "STUPA Events der Hochschule Reutlingen"
MAX_DESCRIPTION = 200
WEEKDAYS = ("Mo.", "Di.", "Mi.", "Do.", "Fr.", "Sa.", "So.")
MONTHS = (
    "Jan.",
    "Feb.",
    "März",
    "Apr.",
    "Mai",
    "Juni",
    "Juli",
    "Aug.",
    "Sept.",
    "Okt.",
    "Nov.",
    "Dez.",
)
STATUS_PREFIX = {"cancelled": "Abgesagt: ", "postponed": "Verschoben: "}
FIXED = {
    "/": (
        "Heute am Campus · STUPA Events",
        "Was heute und in den nächsten Tagen an der Hochschule Reutlingen los ist: "
        "Partys, Kino, Workshops und mehr.",
    ),
    "/suche": (
        "Suche · STUPA Events",
        "Alle Veranstaltungen der Studierendenschaft durchsuchen und nach Kategorie, "
        "Organisation und Zeit filtern.",
    ),
    "/kalender": (
        "Kalender · STUPA Events",
        "Der Monatskalender aller Veranstaltungen der Studierendenschaft "
        "der Hochschule Reutlingen.",
    ),
    "/rueckblick": (
        "Rückblick · STUPA Events",
        "Fotos und Rückblicke auf vergangene Veranstaltungen der Studierendenschaft.",
    ),
    "/start": (
        "Get started · STUPA Events",
        "In wenigen Fragen zum eigenen Kalender der Hochschule Reutlingen: "
        "Interessen wählen, abonnieren, auf Wunsch auch per Mail.",
    ),
    "/abos": (
        "Kalender abonnieren · STUPA Events",
        "Alle Veranstaltungen oder eine Kategorie als Kalender abonnieren "
        "und die wöchentliche Mail verwalten.",
    ),
}
CATEGORY_FALLBACK = "Veranstaltungen dieser Kategorie an der Hochschule Reutlingen."
NOT_FOUND = ("Nicht gefunden · STUPA Events", "Diese Seite gibt es nicht oder nicht mehr.")


@dataclass(frozen=True, slots=True)
class Item:
    """One link of the noscript list."""

    href: str
    label: str


@dataclass(frozen=True, slots=True)
class Page:
    """The shell's description of one URL."""

    path: str
    title: str
    description: str
    image: str | None = None
    image_size: tuple[int, int] = (1200, 630)
    image_alt: str = DEFAULT_ALT
    calendars: tuple[Item, ...] = ()
    jsonld: str | None = None
    noindex: bool = False
    heading: str | None = None
    items: tuple[Item, ...] = ()
    facts: tuple[str, ...] = ()
    summary: str | None = None
    ticket: str | None = None


def when(row: Row[Any]) -> str:
    """Return `Do., 22. Okt. 2026, 20:00` (no time for an all-day event)."""
    local = row.starts_at.astimezone(BERLIN)
    text = f"{WEEKDAYS[local.weekday()]}, {local.day}. {MONTHS[local.month - 1]} {local.year}"
    return text if row.all_day else f"{text}, {local:%H:%M}"


def short_when(card: PublicEventCard) -> str:
    """Return `Do., 22. Okt., 20:00` for a list line."""
    local = card.starts_at.astimezone(BERLIN)
    text = f"{WEEKDAYS[local.weekday()]}, {local.day}. {MONTHS[local.month - 1]}"
    return text if card.all_day else f"{text}, {local:%H:%M}"


def clip(text: str, limit: int = MAX_DESCRIPTION) -> str:
    """Cut a text at a word boundary below `limit` characters, with an ellipsis."""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:. ") + "…"


def fixed_page(path: str, base_url: str) -> Page:
    """Describe one of the fixed pages `/`, `/suche`, `/kalender`, `/rueckblick`."""
    title, description = FIXED[path]
    return Page(path=path, title=title, description=description, image=base_url + DEFAULT_IMAGE)


def event_page(row: Row[Any], base_url: str) -> Page:
    """Describe the detail page of one event."""
    prefix = STATUS_PREFIX.get(row.public_status, "")
    place = f" · {row.venue_name}" if row.venue_name else ""
    lead = f"{when(row)}{place}."
    description = clip(f"{lead} {row.summary}" if row.summary else lead)
    images = image_set(row)
    facts = [when(row)]
    if row.venue_name:
        facts.append(row.venue_name)
    facts.append(row.organization_name)
    return Page(
        path=f"/e/{row.slug}",
        title=f"{prefix}{row.title}",
        description=description,
        image=base_url + (images.og.url if images else DEFAULT_IMAGE),
        image_size=(images.og.width, images.og.height) if images else (1200, 630),
        image_alt=(images.alt or row.title) if images else DEFAULT_ALT,
        calendars=(Item(f"/ics/e/{row.slug}.ics", row.title),),
        jsonld=serialize(event_data(row, base_url)),
        heading=f"{prefix}{row.title}",
        facts=tuple(facts),
        summary=row.summary,
        ticket=row.ticket_url,
    )


def category_page(
    slug: str,
    name: str,
    description: str | None,
    base_url: str,
    upcoming: list[PublicEventCard],
) -> Page:
    """Describe a category page with its upcoming events."""
    return Page(
        path=f"/k/{slug}",
        title=f"{name} · {SITE}",
        description=clip(description or CATEGORY_FALLBACK),
        image=base_url + DEFAULT_IMAGE,
        calendars=(Item(f"/ics/k/{slug}.ics", name),),
        heading=name,
        items=list_items(upcoming),
    )


def list_items(cards: list[PublicEventCard]) -> tuple[Item, ...]:
    """The noscript list of a page: one link per event."""
    return tuple(Item(c.path, f"{c.title} ({short_when(c)})") for c in cards)


def home_page(base_url: str, cards: list[PublicEventCard]) -> Page:
    """Describe the start page with today's and the next events in its noscript list."""
    page = fixed_page("/", base_url)
    return replace(page, heading="Heute am Campus", items=list_items(cards))


def not_found_page(path: str, base_url: str) -> Page:
    """Describe the 404 shell: SPA markup, status 404, never indexed."""
    title, description = NOT_FOUND
    return Page(
        path=path,
        title=title,
        description=description,
        image=base_url + DEFAULT_IMAGE,
        noindex=True,
    )
