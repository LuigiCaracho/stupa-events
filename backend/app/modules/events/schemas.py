"""Schemas of the event API (camelCase on the wire, `extra=forbid`).

Rules of the contract: `title` 1 to 200 characters, `summary` at most 200 characters of
plain text, aware datetimes only, `endsAt >= startsAt`, no control characters in the one-line
fields, links `https://` without user part, `tzid` only `Europe/Berlin` and no `allDay`
before M5. `EventOut` carries the version, the allowed actions and the editable fields.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, Field, model_validator

from app.modules.auth.schemas import CamelModel
from app.modules.dossier.schemas import AttachmentOut
from app.modules.events.states import PublicStatus
from app.modules.followup.schemas import OutcomeOut
from app.modules.formats.schemas import FormatRef
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
ActionName = Literal[
    "publish",
    "unpublish",
    "archive",
    "restore",
    "cancel",
    "postpone",
    "reinstate",
    "revert-revision",
    "confirm-location",
    "verify-howto",
    "save-as-format",
    "clone",
]
PublicReasonCode = Literal["none", "room", "speaker", "illness", "registration", "weather", "other"]
_URL = re.compile(r"^https://[^/@\s]+\.[^/@\s]+")


class EventCreate(CamelModel):
    """Body of `POST /events`: a draft in the organization `organizationId`.

    A timed event needs `startsAt`; an all-day event needs `startsOn` (and optionally
    `endsOn`, the last day) and takes its instants from the days.
    """

    title: Title
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    tzid: Literal["Europe/Berlin"] = "Europe/Berlin"
    all_day: bool = False
    starts_on: date | None = None
    ends_on: date | None = None
    organization_id: UUID
    venue_id: UUID | None = None
    venue_text: VenueText = None
    primary_category_id: UUID | None = None
    summary: Summary = None
    description_md: Description = None
    cost_text: CostText = None
    ticket_url: Link = None
    website_url: Link = None

    @model_validator(mode="after")
    def _times(self) -> Self:
        if self.all_day:
            if self.starts_on is None:
                raise ValueError("startsOn is required for an all-day event")
            if self.starts_at is not None or self.ends_at is not None:
                raise ValueError("startsAt and endsAt follow from startsOn and endsOn")
            if self.ends_on is not None and self.ends_on < self.starts_on:
                raise ValueError("endsOn must not be before startsOn")
            return self
        if self.starts_at is None:
            raise ValueError("startsAt is required")
        if self.starts_on is not None or self.ends_on is not None:
            raise ValueError("startsOn and endsOn need allDay")
        if self.ends_at is not None and self.ends_at < self.starts_at:
            raise ValueError("endsAt must not be before startsAt")
        return self


class DraftFields(CamelModel):
    """The fields of a `PATCH` that an autosave draft may hold (every field optional)."""

    title: Title | None = None
    starts_at: AwareDatetime | None = None
    ends_at: AwareDatetime | None = None
    all_day: bool | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    venue_id: UUID | None = None
    venue_text: VenueText = None
    primary_category_id: UUID | None = None
    summary: Summary = None
    description_md: Description = None
    cost_text: CostText = None
    ticket_url: Link = None
    website_url: Link = None


class EventPatch(DraftFields):
    """Body of `PATCH /events/{id}`: `rev` or `If-Match` names the version, `note` the change.

    `organizationId` is for the editorial team and only while the dossier has none.
    """

    organization_id: UUID | None = None
    rev: int | None = Field(default=None, ge=1)
    note: Note = None


class CancelIn(CamelModel):
    """Body of `cancel`."""

    reason: Note = None
    public_reason_code: PublicReasonCode = "none"
    public_reason_text: Annotated[
        str | None, Field(max_length=140), AfterValidator(_clean_optional)
    ] = None


class PostponeIn(CancelIn):
    """Body of `postpone`."""

    new_starts_at: AwareDatetime | None = None
    new_ends_at: AwareDatetime | None = None


class ReinstateIn(CamelModel):
    """Body of `reinstate`."""

    reason: Note = None


class RevertIn(CamelModel):
    """Body of `actions/revert-revision`."""

    rev: int = Field(ge=1)
    note: Note = None


class EmptyIn(CamelModel):
    """Body of the actions without parameters."""


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
    starts_on: date | None
    ends_on: date | None
    organization: OrgRef | None
    venue_id: UUID | None
    venue: VenueRef | None
    venue_text: str | None
    primary_category: CategoryRef | None
    cost_text: str | None
    ticket_url: str | None
    website_url: str | None
    public_reason: PublicReasonOut | None
    end_estimated: bool
    poster: AttachmentOut | None
    rev: int
    created_by: str
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[ActionName]
    editable_fields: list[str]
    hint_count: int
    checklist_recomputed: int | None = None
    outcome: OutcomeOut | None = None
    howto_verified_at: datetime | None = None
    howto_verified_by: str | None = None
    howto_unverified: bool = False
    format_id: UUID | None = None
    format: FormatRef | None = None
    derived_from_id: UUID | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    facts_dropped: list[str] | None = None
    location_precision: Literal["exact", "building", "hidden"] = "hidden"
    location_confirmed_at: datetime | None = None


class HintOut(CamelModel):
    """One hint of `missing_info`: the code, its weight and the field it points to."""

    code: str
    severity: Literal["info", "warn"]
    field: str | None


class HintsOut(CamelModel):
    """The hints of a dossier."""

    items: list[HintOut]
