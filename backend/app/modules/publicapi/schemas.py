"""The public wire shapes of the feed. Nothing else leaves the public API (PLAN 8.1).

Responses are built field by field from view rows. There is no ORM `model_dump` here, and
the unit test `test_public_schema_lint` keeps it that way.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.modules.auth.schemas import CamelModel


class PublicOrganization(CamelModel):
    """The organizer: slug, name and short name only, no contact data.

    The slug is the value of the feed filter `?org=`.
    """

    id: UUID
    slug: str
    name: str
    short: str


class PublicCategory(CamelModel):
    """A category of the event."""

    slug: str
    name: str
    kind: Literal["format", "fachschaft", "partner"]


class PublicImage(CamelModel):
    """The card image of the event."""

    url: str
    width: int
    height: int
    alt: str
    credit: str


class PublicEventOut(CamelModel):
    """One event of the feed."""

    id: UUID
    slug: str
    title: str
    summary: str | None
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    tzid: str
    status: Literal["scheduled", "cancelled", "postponed"]
    organization: PublicOrganization
    venue_text: str | None
    categories: list[PublicCategory]
    image: PublicImage | None
    url: str


class FeedOut(CamelModel):
    """The feed envelope, schema version 2."""

    schema_version: int = Field(default=2, alias="schema")
    generated_at: datetime
    items: list[PublicEventOut]
