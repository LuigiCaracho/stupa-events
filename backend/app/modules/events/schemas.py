"""Schemas of the event API (camelCase on the wire, `extra=forbid`).

Rules of the contract: `title` 1 to 200 characters, `summary` at most 200 characters of
plain text, aware datetimes only, `endsAt >= startsAt`, no control characters in the one-line
fields, links `https://` without user part, `tzid` only `Europe/Berlin` and no `allDay`
before M5. `EventOut` carries the version, the allowed moves and the field locks.
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
from app.modules.taxonomy.schemas import CategoryRef, VenueRef

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
CostText = Annotated[str | None, Field(max_length=200), AfterValidator(_clean_optional)]
Note = Annotated[str | None, Field(max_length=500)]


def _https_url(value: str | None) -> str | None:
    if value is None:
        return None
    value = _clean_line(value)
    if not value:
        return None
    if len(value) > 500 or not _URL.match(value):
        raise ValueError("a link must start with https:// and name a host")
    return value


Link = Annotated[str | None, AfterValidator(_https_url)]
TransitionName = Literal[
    "T01",
    "T02",
    "T03",
    "T04",
    "T05",
    "T06",
    "T07",
    "T08",
    "T08b",
    "T09",
    "T09b",
    "T10",
    "T11",
    "T12",
]
ActionName = Literal[
    "cancel",
    "postpone",
    "reinstate",
    "image-exception",
    "assign-organization",
    "revert-revision",
    "acknowledge-changes",
    "confirm-flyer",
    "postpone-with-date",
    "public-text",
]
PublicReasonCode = Literal["none", "room", "speaker", "illness", "registration", "weather", "other"]
LockReason = Literal["in_review", "approved", "live_critical", "closed"]
_URL = re.compile(r"^https://[^/@\s]+\.[^/@\s]+")


def _reject_all_day(value: bool) -> bool:
    if value:
        raise ValueError("all-day events arrive with M5")
    return value


NoAllDay = Annotated[bool, AfterValidator(_reject_all_day)]


class EventCreate(CamelModel):
    """Body of `POST /events` (T00): without `organizationId` it is a proposal (E09)."""

    title: Title
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    tzid: Literal["Europe/Berlin"] = "Europe/Berlin"
    all_day: NoAllDay = False
    organization_id: UUID | None = None
    venue_id: UUID | None = None
    venue_text: VenueText = None
    primary_category_id: UUID | None = None
    summary: Summary = None
    description_md: Description = None
    cost_text: CostText = None
    ticket_url: Link = None
    website_url: Link = None

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("endsAt must not be before startsAt")
        return self


class DraftFields(CamelModel):
    """The fields of a `PATCH` that an autosave draft may hold (every field optional)."""

    title: Title | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    all_day: NoAllDay | None = None
    venue_id: UUID | None = None
    venue_text: VenueText = None
    primary_category_id: UUID | None = None
    summary: Summary = None
    description_md: Description = None
    cost_text: CostText = None
    ticket_url: Link = None
    website_url: Link = None


class EventPatch(DraftFields):
    """Body of `PATCH /events/{id}`: `rev` or `If-Match` names the version, `note` the change."""

    rev: int | None = Field(default=None, ge=1)
    note: Note = None


class TransitionIn(CamelModel):
    """Body of a transition: a note (mandatory for five of them) and, for T04, `publishAt`."""

    note: Note = None
    publish_at: AwareDatetime | None = None


class ImageExceptionIn(CamelModel):
    """Body of the image exception action."""

    reason: Annotated[str, Field(min_length=10, max_length=500), AfterValidator(str.strip)]

    @model_validator(mode="after")
    def _long_enough(self) -> Self:
        if len(self.reason) < 10:
            raise ValueError("the reason needs at least 10 characters")
        return self


class CancelIn(CamelModel):
    """Body of `actions/cancel`."""

    reason: Note = None
    public_reason_code: PublicReasonCode = "none"
    public_reason_text: Annotated[
        str | None, Field(max_length=140), AfterValidator(_clean_optional)
    ] = None


class PostponeIn(CancelIn):
    """Body of `actions/postpone`."""

    new_starts_at: AwareDatetime | None = None
    new_ends_at: AwareDatetime | None = None


class ReinstateIn(CamelModel):
    """Body of `actions/reinstate`."""

    reason: Note = None


class AssignOrganizationIn(CamelModel):
    """Body of `actions/assign-organization`."""

    organization_id: UUID


class RevertIn(CamelModel):
    """Body of `actions/revert-revision`."""

    rev: int = Field(ge=1)
    note: Note = None


class EmptyIn(CamelModel):
    """Body of the actions without parameters."""


class ImageExceptionOut(CamelModel):
    """Who granted the image exception, why and when."""

    granted_by: str
    reason: str
    at: datetime


class PublicReasonOut(CamelModel):
    """The public reason of a cancellation or postponement."""

    code: PublicReasonCode
    text: str | None


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
    venue_id: UUID | None
    venue: VenueRef | None
    venue_text: str | None
    primary_category: CategoryRef | None
    cost_text: str | None
    ticket_url: str | None
    website_url: str | None
    publish_at: datetime | None
    public_reason: PublicReasonOut | None
    end_estimated: bool
    text_reviewed_rev: int
    published_rev: int | None
    flyer_checked_at: datetime | None
    poster: AttachmentOut | None
    image_exception: ImageExceptionOut | None
    rev: int
    created_by: str
    submitted_by: str | None
    approved_by: str | None
    created_at: datetime
    updated_at: datetime
    allowed_transitions: list[TransitionName]
    allowed_actions: list[ActionName]
    editable_fields: list[str]
    lock_reason: LockReason | None
