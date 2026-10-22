"""The wire shapes of the site routes under `/api/public/` (events, today, categories, calendar).

Built field by field from view rows by `query/cards.py`; every field is named in
`allowlist.PUBLIC_FIELDS`. All URLs are root-relative (`/e/<slug>`, `/api/public/media/<id>.webp`)
so the SPA stays on its own origin. `tests/schema/public-site-v1.json` is the contract.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from app.modules.auth.schemas import CamelModel
from app.modules.publicapi.schemas import (
    PublicCategory,
    PublicFormat,
    PublicStatusReason,
    PublicVenue,
)


class PublicOrganizationRef(CamelModel):
    """The organizer without its id."""

    slug: str
    name: str
    short: str


class PublicImageVariant(CamelModel):
    """One size of the poster."""

    url: str
    width: int
    height: int


class PublicImageSet(CamelModel):
    """The poster in the sizes of a detail page: thumbnail, card and Open Graph image."""

    thumb: PublicImageVariant
    card: PublicImageVariant
    og: PublicImageVariant
    alt: str
    credit: str


class PublicCardImage(CamelModel):
    """The thumbnail of a list card."""

    url: str
    width: int
    height: int
    alt: str


class PublicEventCore(CamelModel):
    """The fields a card and a detail page share."""

    slug: str
    title: str
    summary: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    starts_on: date | None
    ends_on: date | None
    tzid: str
    status: Literal["scheduled", "cancelled", "postponed"]
    status_reason: PublicStatusReason | None
    organization: PublicOrganizationRef
    venue_name: str | None
    categories: list[PublicCategory]
    path: str


class PublicEventCard(PublicEventCore):
    """One event in a list."""

    image: PublicCardImage | None


class PublicEventDetail(PublicEventCore):
    """One event with everything the public may read."""

    image: PublicImageSet | None
    description_html: str | None
    venue: PublicVenue | None
    venue_text: str | None
    ticket_url: str | None
    website_url: str | None
    cost_text: str | None
    format: PublicFormat | None
    ics_url: str
    is_past: bool
    updated_at: datetime
    sequence: int
    more: list[PublicEventCard]


class PublicFacetCategory(CamelModel):
    """A category with the number of matching events."""

    slug: str
    name: str
    count: int


class PublicFacetOrganization(CamelModel):
    """An organization with the number of matching events."""

    slug: str
    name: str
    short: str
    count: int


class PublicFacetMonth(CamelModel):
    """A Berlin month (`YYYY-MM`) with the number of matching events."""

    month: str
    count: int


class PublicFacets(CamelModel):
    """The disjunctive facets of a search."""

    categories: list[PublicFacetCategory]
    organizations: list[PublicFacetOrganization]
    months: list[PublicFacetMonth]


class PublicSearchOut(CamelModel):
    """A page of events; `total` and `facets` only on the first page."""

    items: list[PublicEventCard]
    next_cursor: str | None
    total: int | None
    facets: PublicFacets | None


class PublicTodayDay(CamelModel):
    """The events that start on one later day."""

    date: date
    items: list[PublicEventCard]


class PublicTodayOut(CamelModel):
    """Today at the campus and the week ahead."""

    generated_at: datetime
    date: date
    today: list[PublicEventCard]
    days: list[PublicTodayDay]
    truncated: bool


class PublicCategoryOut(CamelModel):
    """A category with its description and the number of upcoming events."""

    slug: str
    name: str
    kind: Literal["format", "fachschaft", "partner"]
    parent_slug: str | None
    description: str | None
    upcoming_count: int


class PublicCalendarEntry(CamelModel):
    """An event as the calendar grid needs it."""

    slug: str
    title: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    starts_on: date | None
    ends_on: date | None
    status: Literal["scheduled", "cancelled", "postponed"]
    category_slug: str | None


class PublicCalendarDay(CamelModel):
    """One Berlin day of the month with its events."""

    date: date
    count: int
    items: list[PublicCalendarEntry]


class PublicCalendarOut(CamelModel):
    """One month of events grouped by Berlin day."""

    month: str
    truncated: bool
    days: list[PublicCalendarDay]


class PublicArchiveOut(CamelModel):
    """Past events with a poster, one year at a time."""

    years: list[int]
    year: int | None
    items: list[PublicEventCard]
    next_cursor: str | None
