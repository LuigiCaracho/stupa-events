"""The public wire shapes of the feed, schema 2. Nothing else leaves the public API (PLAN 8.1).

Responses are built field by field from view rows. There is no ORM `model_dump` here, and
the unit test `test_public_allowlist` keeps it that way: a new field fails the test until
`allowlist.py` names it (E39). The JSON schema `tests/schema/feed-v2.json` is the contract.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.modules.auth.schemas import CamelModel


class PublicOrganization(CamelModel):
    """The organizer: slug, name and short name only, no contact data.

    The slug is the value of the feed filter `?organization=`.
    """

    id: UUID
    slug: str
    name: str
    short: str


class PublicCategory(CamelModel):
    """A category of the event: the main one first, then its parent."""

    slug: str
    name: str
    kind: Literal["format", "fachschaft", "partner"]


class PublicFormat(CamelModel):
    """The format an event belongs to (Movienight, Campusfest)."""

    slug: str
    title: str


class PublicVenue(CamelModel):
    """The public place: a name, an address for exact venues, a city for exact and building."""

    name: str
    address: str | None
    city: str | None


class PublicImage(CamelModel):
    """The card image of the event."""

    url: str
    width: int
    height: int
    alt: str
    credit: str


class PublicStatusReason(CamelModel):
    """Why an event is cancelled or postponed: a fixed code and a short public text."""

    code: Literal["none", "room", "speaker", "illness", "registration", "weather", "other"]
    text: str | None


class PublicEventOut(CamelModel):
    """One event of the feed."""

    id: UUID
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
    organization: PublicOrganization
    venue_text: str | None
    venue: PublicVenue | None
    status_reason: PublicStatusReason | None
    categories: list[PublicCategory]
    format: PublicFormat | None
    image: PublicImage | None
    ticket_url: str | None
    website_url: str | None
    cost_text: str | None
    text_html: str | None
    sequence: int
    updated_at: datetime
    url: str


class FeedOut(CamelModel):
    """The feed envelope, schema version 2."""

    schema_version: int = Field(default=2, alias="schema")
    generated_at: datetime
    next_cursor: str | None
    items: list[PublicEventOut]
