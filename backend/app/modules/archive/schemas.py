"""Wire shapes of the archive: the read-only dossier, the clone, "last time" and template cards."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime

from app.modules.archive.carry_over import CarryOverLine
from app.modules.auth.schemas import CamelModel
from app.modules.dossier.schemas import AttachmentOut
from app.modules.dossier.schemas_documents import DocumentItem
from app.modules.events.schemas import EventOut
from app.modules.formats.schemas import FormatRef, OrgBrief
from app.modules.taxonomy.schemas import CategoryRef


class CloneIn(CamelModel):
    """Body of `POST /events/{id}/clone`: the new start and, optionally, end, owner and title."""

    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    organization_id: UUID | None = None
    title: str | None = None


class SourceRef(CamelModel):
    """The dossier a "last time" panel comes from."""

    id: UUID
    title: str
    starts_at: datetime
    state: str
    organization: OrgBrief
    own: bool


class RetrospectiveOut(CamelModel):
    """The retrospective text of the source."""

    id: UUID
    rev: int
    body_md: str


class LastTimeOut(CamelModel):
    """What happened last time: attendance and, for an own source, costs, revenue and notes."""

    source: SourceRef
    attendance: int | None
    costs_cents: int | None
    revenue_cents: int | None
    notes: str | None
    retrospective: RetrospectiveOut | None
    restricted: bool


class ClonePreviewOut(CamelModel):
    """The report of a clone before it happens, with the "last time" of the template."""

    report: list[CarryOverLine]
    last_time: LastTimeOut | None


class CloneOut(CamelModel):
    """The new dossier and what was taken over."""

    event: EventOut
    report: list[CarryOverLine]


class ArchiveEventOut(CamelModel):
    """The core data of an archived dossier, as a person of another organization sees it."""

    id: UUID
    title: str
    summary: str | None
    description_md: str | None
    state: str
    starts_at: datetime
    ends_at: datetime
    all_day: bool
    organization: OrgBrief
    category: CategoryRef | None
    format: FormatRef | None
    venue_name: str | None
    attendance: int | None
    documents: list[DocumentItem]
    attachments: list[AttachmentOut]
    own: bool


class TemplateCard(CamelModel):
    """A dossier that may serve as a template, with the facts that help to choose."""

    id: UUID
    title: str
    starts_at: datetime
    all_day: bool
    state: str
    organization: OrgBrief
    format: FormatRef | None
    categories: list[CategoryRef]
    attendance: int | None
    howto_verified_at: datetime | None
    howto_unverified: bool
    has_howto: bool
    foreign: bool
    shared_documents: int
    checklist_items: int
