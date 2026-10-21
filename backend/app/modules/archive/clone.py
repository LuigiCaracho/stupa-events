"""Clone a template dossier into a new idea (E11, PLAN 7.4).

The clone is one transaction: the dossier with its first revision and status event, the
copied documents with their first revision and the copied checklist. What travels is decided
by `carry_over.RULES`; this module only applies it. Files never travel: no poster, no
attachment, no quote. The caller commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive import carry_over
from app.modules.archive.access import ArchiveRead, load_archive_readable
from app.modules.archive.carry_over import CarryOverLine, Relation, SourceCounts
from app.modules.archive.clonable import is_clonable
from app.modules.archive.schemas import CloneIn
from app.modules.archive.strip_edition import strip_edition
from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.dossier import documents
from app.modules.dossier.checklist_due import due_at_for
from app.modules.dossier.models_checklist import ChecklistItem
from app.modules.dossier.models_documents import Document
from app.modules.events import allday, revisions
from app.modules.events.models import Event
from app.modules.files.access import visibility_readable
from app.modules.formats.models import Format
from app.modules.media.ref_sync import add_refs
from app.modules.media.refs import strip_image_refs
from app.modules.orgs.models import Organization
from app.modules.orgs.scope import bind, org_ids_for
from app.shared.errors import ConflictError, FieldError, NotFoundError, ValidationProblem
from app.shared.timeutil import to_local

COPIED_KINDS = ("howto", "notes", "mail_template")
OFFSET_LIMIT = 365


@dataclass(frozen=True, slots=True)
class CloneResult:
    """The new dossier, the report of what travelled and how many due dates were set."""

    event: Event
    report: list[CarryOverLine]
    recomputed: int


@dataclass(frozen=True, slots=True)
class SourceParts:
    """The rows of the template that a clone would copy."""

    documents: list[Document]
    checklist: list[ChecklistItem]
    howto_linked: bool

    def counts(self) -> SourceCounts:
        """Reduce the rows to the counts of the report."""
        return SourceCounts(len(self.documents), self.howto_linked, len(self.checklist))


def relation_of(read: ArchiveRead) -> Relation:
    """Name the relation of the reader to the template."""
    return "own" if read.own else "foreign"


async def load_template(session: AsyncSession, principal: Principal, event_id: UUID) -> ArchiveRead:
    """Load a template for reading and refuse a dossier that may not be one (409).

    Raises:
        NotFoundError: The dossier is invisible to the caller.
        ConflictError: `not_a_template` for a state that is no template for this reader.
    """
    read = await load_archive_readable(session, principal, event_id)
    if not is_clonable(read.event.state, read.own):
        raise ConflictError("Vorlage nicht mehr verfügbar.", code="not_a_template")
    return read


async def source_parts(
    session: AsyncSession, principal: Principal, read: ArchiveRead
) -> SourceParts:
    """Select the documents and checklist items of the template that the reader may take."""
    source = read.event
    master = await _has_master_howto(session, source)
    rows = await session.scalars(
        select(Document).where(
            Document.event_id == source.id,
            Document.carry_over.is_(True),
            Document.kind.in_(COPIED_KINDS),
        )
    )
    allowed = [
        d
        for d in rows
        if (
            visibility_readable(principal, source.organization_id, d.visibility)
            if read.own
            else d.visibility == "shared"
        )
        and not (master and d.kind == "howto")
    ]
    items = select(ChecklistItem).where(ChecklistItem.event_id == source.id)
    if not read.own:
        items = items.where(ChecklistItem.template_item_id.is_not(None))
    checklist = list(await session.scalars(items.order_by(ChecklistItem.position)))
    return SourceParts(sorted(allowed, key=lambda d: (d.kind, d.title)), checklist, master)


async def _has_master_howto(session: AsyncSession, source: Event) -> bool:
    fmt = await session.get(Format, source.format_id) if source.format_id else None
    return fmt is not None and fmt.master_howto_document_id is not None


async def target_organization(
    session: AsyncSession, principal: Principal, fallback: UUID | None, wanted: UUID | None
) -> UUID:
    """Pick the organization of a new dossier and check `event.create` there.

    `wanted` wins; else `fallback` (the organization of the template or the format) when the
    caller may create there; else the only organization where the caller may create.

    Raises:
        NotFoundError: The organization is unknown, inactive or not creatable for the caller.
        ValidationProblem: `organization_required` when several organizations remain.
    """
    await bind(session, principal)
    if wanted is None and principal.has("event.create", fallback):
        wanted = fallback
    if wanted is None:
        scope = await org_ids_for(session, principal, "event.create")
        if scope is None or len(scope) != 1:
            raise ValidationProblem(
                "Organisation wählen.",
                code="organization_required",
                errors=[FieldError(field="organizationId", msg="required")],
            )
        wanted = next(iter(scope))
    org = await session.get(Organization, wanted)
    if org is None or not org.active or not principal.has("event.create", org.id):
        raise NotFoundError("organization not found")
    return org.id


def clone_times(source: Event, body: CloneIn) -> tuple[datetime, datetime, bool, tuple | None]:
    """Compute `(starts_at, ends_at, end_estimated, days)` of the clone.

    A timed template keeps its duration; an all-day template keeps its number of days
    and starts on the local day of `startsAt`.
    """
    if source.all_day:
        assert source.starts_on is not None and source.ends_on is not None
        first = to_local(body.starts_at, source.tzid).date()
        last = first + (source.ends_on - source.starts_on)
        start, end = allday.bounds(first, last, source.tzid)
        return start, end, False, (first, last)
    end = body.ends_at or body.starts_at + (source.ends_at - source.starts_at)
    if end < body.starts_at:
        raise ValidationProblem(
            "endsAt must not be before startsAt.",
            errors=[FieldError(field="endsAt", msg="before startsAt")],
        )
    return body.starts_at, end, body.ends_at is None and source.end_estimated, None


def offset_of(item: ChecklistItem, source: Event) -> int | None:
    """Return the due offset of an item in days; derive it from a hand-set date when needed."""
    if item.due_offset_days is not None or item.due_at is None:
        return item.due_offset_days
    delta = (
        to_local(item.due_at, source.tzid).date() - to_local(source.starts_at, source.tzid).date()
    ).days
    return max(-OFFSET_LIMIT, min(OFFSET_LIMIT, delta))


def new_event(
    principal: Principal, source: Event, body: CloneIn, org_id: UUID, relation: Relation
) -> Event:
    """Build the unsaved dossier of the clone from the template and the request."""
    starts_at, ends_at, estimated, days = clone_times(source, body)
    return Event(
        state="idea",
        title=(body.title or "").strip() or strip_edition(source.title),
        summary=source.summary,
        description_md=(
            source.description_md if relation == "own" else strip_image_refs(source.description_md)
        ),
        cost_text=source.cost_text,
        primary_category_id=source.primary_category_id,
        format_id=source.format_id,
        venue_id=source.venue_id,
        venue_text=source.venue_text,
        location_precision="hidden",
        facts=carry_over.reset_facts(source.facts, relation),
        organization_id=org_id,
        starts_at=starts_at,
        ends_at=ends_at,
        end_estimated=estimated,
        tzid=source.tzid,
        all_day=source.all_day,
        starts_on=days[0] if days else None,
        ends_on=days[1] if days else None,
        derived_from_id=source.id,
        origin_kind="internal",
        created_by=principal.sub,
        rev=1,
        public_seq=0,
    )


async def _copy_documents(
    session: AsyncSession,
    principal: Principal,
    event: Event,
    parts: SourceParts,
    source: Event,
    relation: Relation,
) -> None:
    note = f"Aus Vorlage „{source.title}“"
    for original in parts.documents:
        visibility = (
            original.visibility
            if relation == "own"
            else documents.DEFAULT_VISIBILITY[original.kind]
        )
        copy = Document(
            event_id=event.id,
            kind=original.kind,
            title=original.title,
            body_md=original.body_md,
            meta=original.meta,
            visibility=visibility,
            carry_over=True,
            created_by=principal.sub,
        )
        await documents.insert_document(session, principal, event, copy, note)


def _copy_checklist(
    session: AsyncSession, principal: Principal, event: Event, parts: SourceParts, source: Event
) -> int:
    recomputed = 0
    for item in parts.checklist:
        offset = offset_of(item, source)
        due = due_at_for(event.starts_at, event.tzid, offset)
        recomputed += due is not None
        session.add(
            ChecklistItem(
                event_id=event.id,
                template_item_id=item.template_item_id,
                position=item.position,
                text=item.text,
                phase=item.phase,
                required=item.required,
                due_offset_days=offset,
                due_at=due,
                due_manual=False,
                created_by=principal.sub,
            )
        )
    return recomputed


async def clone_event(
    session: AsyncSession, principal: Principal, source_id: UUID, body: CloneIn
) -> CloneResult:
    """Create the dossier of a new edition from a template (no commit).

    Raises:
        NotFoundError: The template or the organization is invisible to the caller.
        ConflictError: `not_a_template`.
        ValidationProblem: `organization_required`, or an end before the start.
    """
    read = await load_template(session, principal, source_id)
    relation = relation_of(read)
    org_id = await target_organization(
        session, principal, read.event.organization_id, body.organization_id
    )
    parts = await source_parts(session, principal, read)
    event = new_event(principal, read.event, body, org_id, relation)
    session.add(event)
    await session.flush()
    await session.refresh(event)
    await add_refs(session, "event", event.id, event.description_md)
    await _copy_documents(session, principal, event, parts, read.event, relation)
    recomputed = _copy_checklist(session, principal, event, parts, read.event)
    await session.flush()
    await revisions.append_revision(
        session,
        event,
        actor=principal.sub,
        field_class="state",
        note=f"Aus Vorlage „{read.event.title}“",
    )
    await revisions.append_status(
        session, event, transition_id="T00", from_state=None, actor=principal.sub
    )
    await revisions.audit(
        session,
        event,
        actor=principal.sub,
        action=AuditAction.EVENT_CLONE,
        data={"sourceId": str(read.event.id), "organizationId": str(org_id)},
    )
    return CloneResult(event, carry_over.plan(relation, parts.counts()), recomputed)


async def preview_clone(
    session: AsyncSession, principal: Principal, source_id: UUID, organization_id: UUID | None
) -> list[CarryOverLine]:
    """Return the report a clone would have, changing nothing."""
    read = await load_template(session, principal, source_id)
    await target_organization(session, principal, read.event.organization_id, organization_id)
    parts = await source_parts(session, principal, read)
    return carry_over.plan(relation_of(read), parts.counts())
