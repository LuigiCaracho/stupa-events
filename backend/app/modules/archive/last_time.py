"""The "last time" panel: what the previous edition drew and cost (E12, A13).

The source is the template the dossier was derived from, else the newest archived edition
of the same format that started earlier. The own organization sees everything; another
organization sees the attendance and a `shared` retrospective, never costs, revenue or notes.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive.access import ArchiveRead, load_archive_readable
from app.modules.archive.schemas import LastTimeOut, RetrospectiveOut, SourceRef
from app.modules.auth.principal import Principal
from app.modules.dossier.models_documents import Document
from app.modules.events.models import Event
from app.modules.files.access import visibility_readable
from app.modules.formats.queries import organizations
from app.shared.errors import NotFoundError


async def _derived(session: AsyncSession, principal: Principal, event: Event) -> ArchiveRead | None:
    if event.derived_from_id is None:
        return None
    try:
        return await load_archive_readable(session, principal, event.derived_from_id)
    except NotFoundError:
        return None


async def _earlier_edition(
    session: AsyncSession, principal: Principal, event: Event
) -> ArchiveRead | None:
    if event.format_id is None:
        return None
    previous = await session.scalar(
        select(Event.id)
        .where(
            Event.format_id == event.format_id,
            Event.state == "archived",
            Event.published_at.is_not(None),
            Event.starts_at < event.starts_at,
            Event.id != event.id,
        )
        .order_by(Event.starts_at.desc())
        .limit(1)
    )
    return await load_archive_readable(session, principal, previous) if previous else None


async def _retrospective(
    session: AsyncSession, principal: Principal, read: ArchiveRead
) -> RetrospectiveOut | None:
    doc = await session.scalar(
        select(Document).where(Document.event_id == read.event.id, Document.kind == "retrospective")
    )
    visible = doc is not None and (
        visibility_readable(principal, read.event.organization_id, doc.visibility)
        if read.own
        else doc.visibility == "shared"
    )
    return (
        RetrospectiveOut(id=doc.id, rev=doc.rev, body_md=doc.body_md) if visible and doc else None
    )


async def panel(session: AsyncSession, principal: Principal, read: ArchiveRead) -> LastTimeOut:
    """Build the panel for a given source: attendance always, the rest for the own organization."""
    source, outcome = read.event, read.event.outcome or {}
    assert source.organization_id is not None
    org = (await organizations(session, {source.organization_id}))[source.organization_id]
    return LastTimeOut(
        source=SourceRef(
            id=source.id,
            title=source.title,
            starts_at=source.starts_at,
            state=source.state,
            organization=org,
            own=read.own,
        ),
        attendance=outcome.get("attendance"),
        costs_cents=outcome.get("costsCents") if read.own else None,
        revenue_cents=outcome.get("revenueCents") if read.own else None,
        notes=outcome.get("notes") if read.own else None,
        retrospective=await _retrospective(session, principal, read),
        restricted=not read.own,
    )


async def last_time(
    session: AsyncSession, principal: Principal, event: Event
) -> LastTimeOut | None:
    """Return the panel for a dossier, or `None` when there was no earlier edition."""
    read = await _derived(session, principal, event) or await _earlier_edition(
        session, principal, event
    )
    return None if read is None else await panel(session, principal, read)
