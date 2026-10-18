"""Schemas of the event API (camelCase on the wire, `extra=forbid`).

Rules of the contract (4.2): `title` 1 to 200 characters, `summary` at most 200
characters of plain text, aware datetimes only, `endsAt >= startsAt`, no control
characters in `title`, `summary` and `venueText`, `tzid` only `Europe/Berlin` and no
`allDay` in M1.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, Field, model_validator

from app.modules.auth.schemas import CamelModel
from app.modules.dossier.schemas import AttachmentOut
from app.modules.events.states import PublicStatus
from app.modules.orgs.schemas import OrgRef
from app.modules.taxonomy.schemas import CategoryRef

_CONTROL = re.compile(r"[\x01-\x1f\x7f-\x9f  ]")


def _clean_line(value: str) -> str:
    if _CONTROL.search(value):
        raise ValueError("control characters are not allowed")
    return value.strip()


def _clean_optional(value: str | None) -> str | None:
    return None if value is None else (_clean_line(value) or None)


Title = Annotated[str, Field(min_length=1, max_length=200), AfterValidator(_clean_line)]
Summary = Annotated[str | None, Field(max_length=200), AfterValidator(_clean_optional)]
VenueText = Annotated[str | None, Field(max_length=200), AfterValidator(_clean_optional)]
Description = Annotated[str | None, Field(max_length=20000)]
TransitionName = Literal["T01", "T02", "T04", "T05"]


def _reject_all_day(value: bool) -> bool:
    if value:
        raise ValueError("all-day events arrive with M5")
    return value


NoAllDay = Annotated[bool, AfterValidator(_reject_all_day)]


class EventCreate(CamelModel):
    """Body of `POST /events` (T00)."""

    title: Title
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    tzid: Literal["Europe/Berlin"] = "Europe/Berlin"
    all_day: NoAllDay = False
    organization_id: UUID
    venue_text: VenueText = None
    primary_category_id: UUID | None = None
    summary: Summary = None
    description_md: Description = None

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.ends_at < self.starts_at:
            raise ValueError("endsAt must not be before startsAt")
        return self


class EventPatch(CamelModel):
    """Body of `PATCH /events/{id}`: `rev` is required, every other field is optional."""

    rev: int = Field(ge=1)
    title: Title | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    all_day: NoAllDay | None = None
    venue_text: VenueText = None
    primary_category_id: UUID | None = None
    summary: Summary = None
    description_md: Description = None


class TransitionIn(CamelModel):
    """Body of a transition: an optional note of at most 500 characters."""

    note: Annotated[str | None, Field(max_length=500)] = None


class ImageExceptionIn(CamelModel):
    """Body of `POST /events/{id}/image-exception`."""

    reason: Annotated[str, Field(min_length=10, max_length=500), AfterValidator(str.strip)]

    @model_validator(mode="after")
    def _long_enough(self) -> Self:
        if len(self.reason) < 10:
            raise ValueError("the reason needs at least 10 characters")
        return self


class ImageExceptionOut(CamelModel):
    """Who granted the image exception, why and when."""

    granted_by: str
    reason: str
    at: datetime


class EventOut(CamelModel):
    """A dossier as the API shows it."""

    id: UUID
    slug: str | None
    state: str
    public_status: PublicStatus
    title: str
    summary: str | None
    description_md: str | None
    starts_at: datetime
    ends_at: datetime
    tzid: str
    all_day: bool
    organization: OrgRef | None
    venue_text: str | None
    primary_category: CategoryRef | None
    poster: AttachmentOut | None
    image_exception: ImageExceptionOut | None
    rev: int
    created_by: str
    submitted_by: str | None
    approved_by: str | None
    created_at: datetime
    updated_at: datetime
    allowed_transitions: list[TransitionName]
