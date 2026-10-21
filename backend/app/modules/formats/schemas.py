"""Wire shapes of formats (I18): cards, the full format, defaults and the edition list."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, Field

from app.modules.auth.schemas import CamelModel
from app.modules.events.models import CONTROL_CHARS
from app.modules.formats.models import SLUG_PATTERN

ChecklistProfile = Literal["generic", "party", "meeting", "trip"]


class FormatRef(CamelModel):
    """The slug and the title of a format, as other shapes embed it."""

    slug: str
    title: str


class FormatDefaults(CamelModel):
    """What a new edition starts with (contract 2.1); the service checks the references."""

    category_id: UUID | None = None
    venue_id: UUID | None = None
    duration_minutes: Annotated[int, Field(ge=15, le=10080)] | None = None
    checklist_profile: ChecklistProfile | None = None


class OrgBrief(CamelModel):
    """Slug, name and short name of an organization."""

    slug: str
    name: str
    short: str


class EditionRef(CamelModel):
    """The id, title and start of one edition."""

    id: UUID
    title: str
    starts_at: datetime


class FormatCard(CamelModel):
    """A format in the list: its organization, its freshness and its editions."""

    slug: str
    title: str
    organization: OrgBrief
    active: bool
    last_verified_at: datetime | None
    howto_stale: bool
    editions: int
    last_edition: EditionRef | None


class MasterHowtoOut(CamelModel):
    """The master howto of a format with its text."""

    id: UUID
    rev: int
    title: str
    verified_at: datetime | None
    verified_by: str | None
    body_md: str


class ChecklistItemBrief(CamelModel):
    """One item of the checklist template of a format profile."""

    text: str
    phase: str
    required: bool
    due_offset_days: int | None


class FormatChecklistOut(CamelModel):
    """The template of the format profile, read-only."""

    profile: ChecklistProfile
    template: dict[str, str]
    items: list[ChecklistItemBrief]


class MailTemplateRef(CamelModel):
    """A mail template of the latest edition, as a link."""

    id: UUID
    title: str
    event_id: UUID


class EditionOut(EditionRef):
    """One edition of a format; foreign editions show no costs."""

    state: str
    attendance: int | None
    costs_cents: int | None
    howto_unverified: bool
    foreign: bool


class FormatOut(CamelModel):
    """A format with its defaults, master howto, checklist template and editions."""

    slug: str
    title: str
    organization: OrgBrief
    active: bool
    description_md: str | None
    defaults: FormatDefaults
    master_howto: MasterHowtoOut | None
    last_verified_at: datetime | None
    last_verified_by: str | None
    howto_stale: bool
    checklist: FormatChecklistOut
    mail_templates: list[MailTemplateRef]
    editions: list[EditionOut]


Slug = Annotated[str, Field(pattern=SLUG_PATTERN)]
Title = Annotated[str, Field(min_length=1, max_length=120), AfterValidator(str.strip)]
Description = Annotated[str | None, Field(max_length=20000)]


def _no_control(value: str) -> str:
    if re.search(CONTROL_CHARS, value):
        raise ValueError("control characters are not allowed")
    return value


CleanTitle = Annotated[Title, AfterValidator(_no_control)]


class FormatCreate(CamelModel):
    """Body of `POST /formats`."""

    slug: Slug
    title: CleanTitle
    organization_id: UUID
    defaults: FormatDefaults = Field(default_factory=FormatDefaults)
    description_md: Description = None


class FormatPatch(CamelModel):
    """Body of `PATCH /formats/{slug}` (the last writer wins)."""

    title: CleanTitle | None = None
    defaults: FormatDefaults | None = None
    description_md: Description = None
    active: bool | None = None


class HowtoCreate(CamelModel):
    """Body of `POST /formats/{slug}/howto`: copy the howto of a dossier, or start a scaffold."""

    from_event_id: UUID | None = None


class NewEditionIn(CamelModel):
    """Body of `POST /formats/{slug}/new-edition`."""

    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    organization_id: UUID | None = None


class SaveAsFormatIn(CamelModel):
    """Body of `POST /events/{id}/save-as-format`."""

    slug: Slug
    title: CleanTitle
    defaults: FormatDefaults | None = None


class FormatLinkIn(CamelModel):
    """Body of `PUT /events/{id}/format`: the slug of the format, or `null` to leave it."""

    slug: Slug | None
