"""Reads of the format pages: cards, editions, the master howto and the profile checklist."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive.clonable import clonable_clause
from app.modules.auth.principal import Principal
from app.modules.dossier.models_checklist import ChecklistTemplate, ChecklistTemplateItem
from app.modules.dossier.models_documents import Document
from app.modules.events.models import Event
from app.modules.formats.models import Format
from app.modules.formats.schemas import (
    ChecklistItemBrief,
    EditionOut,
    EditionRef,
    FormatCard,
    FormatChecklistOut,
    MailTemplateRef,
    MasterHowtoOut,
    OrgBrief,
)
from app.modules.orgs.models import Organization
from app.modules.orgs.scope import readable_org_ids
from app.shared.search import escape_like
from app.shared.timeutil import utcnow

STALE_AFTER = timedelta(days=365)
EDITION_LIMIT = 50


def howto_stale(last_verified_at: datetime | None, now: datetime) -> bool:
    """Tell if the format's howto was never verified or not for twelve months (PLAN 7.3)."""
    return last_verified_at is None or last_verified_at < now - STALE_AFTER


async def organizations(session: AsyncSession, ids: set[UUID]) -> dict[UUID, OrgBrief]:
    """Read the organization briefs of `ids` in one query."""
    rows = await session.scalars(select(Organization).where(Organization.id.in_(ids)))
    return {o.id: OrgBrief(slug=o.slug, name=o.name, short=o.short) for o in rows}


async def list_cards(
    session: AsyncSession,
    principal: Principal,
    *,
    q: str | None,
    organization: str | None,
    limit: int,
    offset: int,
) -> tuple[list[FormatCard], int]:
    """Return one page of active formats and the total, with edition counts and freshness."""
    scope = await readable_org_ids(session, principal)
    query = select(Format).where(Format.active.is_(True))
    if q:
        pattern = f"%{escape_like(q.strip())}%"
        query = query.where(
            or_(Format.title.ilike(pattern, escape="\\"), Format.slug.ilike(pattern, escape="\\"))
        )
    if organization:
        query = query.where(
            Format.organization_id
            == select(Organization.id).where(Organization.slug == organization).scalar_subquery()
        )
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    formats = list(
        await session.scalars(query.order_by(Format.title, Format.id).limit(limit).offset(offset))
    )
    editions = await _edition_stats(session, [f.id for f in formats], scope)
    orgs = await organizations(session, {f.organization_id for f in formats})
    now = utcnow()
    cards = [
        FormatCard(
            slug=f.slug,
            title=f.title,
            organization=orgs[f.organization_id],
            active=f.active,
            last_verified_at=f.last_verified_at,
            howto_stale=howto_stale(f.last_verified_at, now),
            editions=editions.get(f.id, (0, None))[0],
            last_edition=editions.get(f.id, (0, None))[1],
        )
        for f in formats
    ]
    return cards, total


async def _edition_stats(
    session: AsyncSession, ids: list[UUID], scope: set[UUID] | None
) -> dict[UUID, tuple[int, EditionRef | None]]:
    rows = await session.execute(
        select(Event.format_id, Event.id, Event.title, Event.starts_at)
        .where(Event.format_id.in_(ids), clonable_clause(scope))
        .order_by(Event.starts_at.desc())
    )
    stats: dict[UUID, tuple[int, EditionRef | None]] = {}
    for format_id, event_id, title, starts_at in rows.all():
        assert format_id is not None
        count, latest = stats.get(format_id, (0, None))
        stats[format_id] = (
            count + 1,
            latest or EditionRef(id=event_id, title=title, starts_at=starts_at),
        )
    return stats


async def editions(
    session: AsyncSession, principal: Principal, fmt: Format
) -> list[tuple[Event, bool]]:
    """Return the readable editions of a format, newest first, each with `foreign`."""
    scope = await readable_org_ids(session, principal)
    rows = await session.scalars(
        select(Event)
        .where(Event.format_id == fmt.id, clonable_clause(scope))
        .order_by(Event.starts_at.desc())
        .limit(EDITION_LIMIT)
    )
    return [(e, scope is not None and e.organization_id not in scope) for e in rows]


def edition_out(event: Event, foreign: bool, has_howto: bool) -> EditionOut:
    """Build an edition; a foreign edition shows the attendance but no costs."""
    outcome = event.outcome or {}
    return EditionOut(
        id=event.id,
        title=event.title,
        starts_at=event.starts_at,
        state=event.state,
        attendance=outcome.get("attendance"),
        costs_cents=None if foreign else outcome.get("costsCents"),
        howto_unverified=event.state == "archived"
        and event.howto_verified_at is None
        and has_howto,
        foreign=foreign,
    )


async def master_howto(session: AsyncSession, fmt: Format) -> MasterHowtoOut | None:
    """Return the master howto with its text, or `None` when the format has none."""
    doc = (
        await session.get(Document, fmt.master_howto_document_id)
        if fmt.master_howto_document_id
        else None
    )
    return (
        None
        if doc is None
        else MasterHowtoOut(
            id=doc.id,
            rev=doc.rev,
            title=doc.title,
            verified_at=doc.verified_at,
            verified_by=doc.verified_by,
            body_md=doc.body_md,
        )
    )


async def profile_checklist(session: AsyncSession, profile: str) -> FormatChecklistOut:
    """Read the checklist template of a profile (falling back to `generic`, seeded by 0005)."""
    template = await session.scalar(
        select(ChecklistTemplate).where(ChecklistTemplate.profile == profile)
    ) or await session.scalar(select(ChecklistTemplate).where(ChecklistTemplate.slug == "generic"))
    assert template is not None
    items = await session.scalars(
        select(ChecklistTemplateItem)
        .where(ChecklistTemplateItem.template_id == template.id)
        .order_by(ChecklistTemplateItem.position)
    )
    return FormatChecklistOut(
        profile=profile,  # type: ignore[arg-type]
        template={"slug": template.slug, "name": template.name},
        items=[
            ChecklistItemBrief(
                text=i.text, phase=i.phase, required=i.required, due_offset_days=i.due_offset_days
            )
            for i in items
        ],
    )


async def latest_mail_templates(
    session: AsyncSession, principal: Principal, fmt: Format
) -> list[MailTemplateRef]:
    """Link the mail templates of the newest readable archived edition (shared ones only)."""
    newest = await session.scalar(
        select(Event.id)
        .where(Event.format_id == fmt.id, Event.state == "archived")
        .order_by(Event.starts_at.desc())
        .limit(1)
    )
    if newest is None:
        return []
    rows = await session.scalars(
        select(Document)
        .where(
            Document.event_id == newest,
            Document.kind == "mail_template",
            Document.visibility == "shared",
        )
        .order_by(Document.title)
    )
    return [MailTemplateRef(id=d.id, title=d.title, event_id=newest) for d in rows]
