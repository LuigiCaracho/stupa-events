"""Formats: create, change, verify, save a dossier as a format, start a new edition (I18).

The service never commits; the router does. A format is never deleted. Changes are not
versioned (the last writer wins); the master howto keeps its revisions as a document.
"""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive import clone as cloning
from app.modules.archive.clonable import clonable_clause
from app.modules.archive.clone import CloneResult
from app.modules.archive.schemas import CloneIn
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.principal import Principal
from app.modules.dossier import checklist
from app.modules.dossier.models_documents import Document
from app.modules.dossier.rules import ensure_permission, load_readable
from app.modules.events import revisions
from app.modules.events.conflict import VersionConflict
from app.modules.events.hints_data import howto_presence
from app.modules.events.models import Event
from app.modules.events.schemas import EventCreate
from app.modules.events.service import EventService
from app.modules.events.writer import update_event
from app.modules.formats import queries
from app.modules.formats.access import ensure_can_manage
from app.modules.formats.defaults import stored_defaults
from app.modules.formats.howto import create_master
from app.modules.formats.models import Format
from app.modules.formats.schemas import (
    FormatCreate,
    FormatDefaults,
    FormatOut,
    FormatPatch,
    NewEditionIn,
    SaveAsFormatIn,
)
from app.modules.formats.verification import touch_format
from app.modules.orgs.models import Organization
from app.modules.orgs.scope import bind, readable_org_ids
from app.modules.taxonomy.models import Category
from app.shared.errors import ConflictError, ForbiddenError, NotFoundError, ValidationProblem
from app.shared.timeutil import utcnow

DEFAULT_MINUTES = 120
MIN_MINUTES, MAX_MINUTES, STEP = 15, 10080, 15


async def load_format(session: AsyncSession, slug: str) -> Format:
    """Load a format by slug, inactive ones included.

    Raises:
        NotFoundError: No format has this slug.
    """
    fmt = await session.scalar(select(Format).where(Format.slug == slug))
    if fmt is None:
        raise NotFoundError("format not found")
    return fmt


async def _audit(
    session: AsyncSession, principal: Principal, action: AuditAction, fmt: Format
) -> None:
    await audit_record(
        session,
        actor=principal.sub,
        action=action,
        target_type="format",
        target_id=str(fmt.id),
        data={"slug": fmt.slug},
    )


async def _insert(session: AsyncSession, principal: Principal, fmt: Format) -> Format:
    session.add(fmt)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise ConflictError("Das Kürzel ist vergeben.", code="slug_taken") from exc
    await session.refresh(fmt)
    await _audit(session, principal, AuditAction.FORMAT_CREATE, fmt)
    return fmt


async def create_format(session: AsyncSession, principal: Principal, body: FormatCreate) -> Format:
    """Create a format in an organization (`format.manage`, or `event.publish` there).

    Raises:
        NotFoundError: The organization is unknown or inactive.
        ForbiddenError: Neither right holds.
        ConflictError: `slug_taken`.
    """
    org = await session.get(Organization, body.organization_id)
    if org is None or not org.active:
        raise NotFoundError("organization not found")
    await bind(session, principal)
    if not (principal.has("format.manage") or principal.has("event.publish", org.id)):
        raise ForbiddenError("Missing permission: format.manage")
    fmt = Format(
        slug=body.slug,
        title=body.title,
        organization_id=org.id,
        defaults=await stored_defaults(session, body.defaults),
        description_md=body.description_md,
        created_by=principal.sub,
    )
    return await _insert(session, principal, fmt)


async def patch_format(
    session: AsyncSession, principal: Principal, slug: str, body: FormatPatch
) -> Format:
    """Change title, defaults, description or `active` (the last writer wins)."""
    fmt = await load_format(session, slug)
    await ensure_can_manage(session, principal, fmt)
    given = body.model_fields_set
    if "title" in given and body.title is not None:
        fmt.title = body.title
    if "defaults" in given and body.defaults is not None:
        fmt.defaults = await stored_defaults(session, body.defaults)
    if "description_md" in given:
        fmt.description_md = body.description_md
    if "active" in given and body.active is not None:
        fmt.active = body.active
    await session.flush()
    await _audit(session, principal, AuditAction.FORMAT_UPDATE, fmt)
    return fmt


async def mark_verified(session: AsyncSession, principal: Principal, slug: str) -> Format:
    """Date the format and its master howto as verified (editorial upkeep)."""
    fmt = await load_format(session, slug)
    await ensure_can_manage(session, principal, fmt)
    await touch_format(session, fmt.id, principal.sub, utcnow())
    await session.refresh(fmt)
    await _audit(session, principal, AuditAction.FORMAT_UPDATE, fmt)
    return fmt


async def format_out(session: AsyncSession, principal: Principal, fmt: Format) -> FormatOut:
    """Build the format page: head, master howto, profile checklist, mails and editions."""
    org = (await queries.organizations(session, {fmt.organization_id}))[fmt.organization_id]
    rows = await queries.editions(session, principal, fmt)
    presence = await howto_presence(session, [event for event, _ in rows])
    defaults = FormatDefaults.model_validate(fmt.defaults)
    return FormatOut(
        slug=fmt.slug,
        title=fmt.title,
        organization=org,
        active=fmt.active,
        description_md=fmt.description_md,
        defaults=defaults,
        master_howto=await queries.master_howto(session, fmt),
        last_verified_at=fmt.last_verified_at,
        last_verified_by=fmt.last_verified_by,
        howto_stale=queries.howto_stale(fmt.last_verified_at, utcnow()),
        checklist=await queries.profile_checklist(session, defaults.checklist_profile or "generic"),
        mail_templates=await queries.latest_mail_templates(session, principal, fmt),
        editions=[queries.edition_out(e, foreign, e.id in presence) for e, foreign in rows],
    )


def _duration_minutes(event: Event) -> int:
    minutes = (event.ends_at - event.starts_at).total_seconds() / 60
    return max(MIN_MINUTES, min(MAX_MINUTES, round(minutes / STEP) * STEP))


async def save_as_format(
    session: AsyncSession, principal: Principal, event_id: UUID, body: SaveAsFormatIn
) -> tuple[Format, Event]:
    """Make a dossier the first edition of a new format and its howto the master howto.

    Raises:
        NotFoundError, ForbiddenError: no read right, or neither `event.publish` nor
            `format.manage`.
        ConflictError: `already_in_format`, `slug_taken`.
        ValidationProblem: `organization_required` for a dossier without an organization.
    """
    event = await load_readable(session, principal, event_id)
    if event.organization_id is None:
        raise ValidationProblem(
            "Das Dossier braucht eine Organisation.", code="organization_required"
        )
    if not (
        principal.has("format.manage") or principal.has("event.publish", event.organization_id)
    ):
        raise ForbiddenError("Missing permission: event.publish")
    if event.format_id is not None:
        raise ConflictError("Das Dossier gehört schon zu einem Format.", code="already_in_format")
    category = (
        await session.get(Category, event.primary_category_id)
        if event.primary_category_id
        else None
    )
    derived = FormatDefaults(
        category_id=event.primary_category_id,
        venue_id=event.venue_id,
        duration_minutes=_duration_minutes(event),
        checklist_profile=category.required_profile if category else "generic",  # type: ignore[arg-type]
    )
    merged = derived.model_copy(
        update=(body.defaults or FormatDefaults()).model_dump(exclude_none=True)
    )
    fmt = await _insert(
        session,
        principal,
        Format(
            slug=body.slug,
            title=body.title,
            organization_id=event.organization_id,
            defaults=await stored_defaults(session, merged),
            created_by=principal.sub,
        ),
    )
    howto = await session.scalar(
        select(Document).where(Document.event_id == event.id, Document.kind == "howto")
    )
    if howto is not None:
        await create_master(session, principal, fmt, event.id)
    updated = await update_event(session, event, {"format_id": fmt.id}, states=[event.state])
    await revisions.append_revision(session, updated, actor=principal.sub)
    return fmt, updated


async def set_event_format(
    session: AsyncSession, principal: Principal, event_id: UUID, slug: str | None, expected_rev: int
) -> Event:
    """Put a dossier into a format (or out of it with `None`); `event.edit` as for any field."""
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, "event.edit")
    fmt = await load_format(session, slug) if slug else None
    if event.rev != expected_rev:
        raise VersionConflict(event)
    updated = await update_event(
        session, event, {"format_id": fmt.id if fmt else None}, states=[event.state]
    )
    await revisions.append_revision(session, updated, actor=principal.sub)
    return updated


async def _latest_template(session: AsyncSession, principal: Principal, fmt: Format) -> UUID | None:
    scope = await readable_org_ids(session, principal)
    return await session.scalar(
        select(Event.id)
        .where(Event.format_id == fmt.id, clonable_clause(scope))
        .order_by(Event.starts_at.desc())
        .limit(1)
    )


async def new_edition(
    session: AsyncSession, principal: Principal, slug: str, body: NewEditionIn
) -> CloneResult:
    """Start the next edition: clone the newest readable edition, else build from the defaults."""
    fmt = await load_format(session, slug)
    template = await _latest_template(session, principal, fmt)
    if template is not None:
        return await cloning.clone_event(
            session,
            principal,
            template,
            CloneIn(
                starts_at=body.starts_at, ends_at=body.ends_at, organization_id=body.organization_id
            ),
        )
    defaults = FormatDefaults.model_validate(fmt.defaults)
    org_id = await cloning.target_organization(
        session, principal, fmt.organization_id, body.organization_id
    )
    minutes = defaults.duration_minutes or DEFAULT_MINUTES
    event = await EventService(session).create(
        principal,
        EventCreate(
            title=fmt.title,
            starts_at=body.starts_at,
            ends_at=body.ends_at or body.starts_at + timedelta(minutes=minutes),
            organization_id=org_id,
            primary_category_id=defaults.category_id,
            venue_id=defaults.venue_id,
        ),
        format_id=fmt.id,
    )
    applied = await checklist.apply_template(
        session, principal, event.id, defaults.checklist_profile or "generic"
    )
    return CloneResult(event, [], applied.added or 0)
