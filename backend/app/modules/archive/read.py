"""The read-only view of an archived dossier: core data, shared documents and files (PLAN 5.4).

An own dossier shows what the caller's rights allow; a foreign archived dossier shows its core
data, its `shared` documents and its clean `shared` attachments, and nothing else: no costs,
no notes, no checklist, no comments, no revisions.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.archive.access import load_archive_readable
from app.modules.archive.schemas import ArchiveEventOut
from app.modules.auth.principal import Principal
from app.modules.dossier.models_documents import Document
from app.modules.dossier.schemas import attachment_out
from app.modules.dossier.schemas_documents import DocumentItem
from app.modules.events.models import Event
from app.modules.files.access import foreign_readable_clause, readable_clause, visibility_readable
from app.modules.files.models import Attachment
from app.modules.formats.models import Format
from app.modules.formats.queries import organizations
from app.modules.formats.schemas import FormatRef
from app.modules.taxonomy.models import Category, Venue
from app.modules.taxonomy.schemas import CategoryRef


async def _venue_name(session: AsyncSession, event: Event, own: bool) -> str | None:
    venue = await session.get(Venue, event.venue_id) if event.venue_id else None
    if venue is not None:
        return venue.name if own or not venue.is_private else None
    shown = own or event.location_precision != "hidden"
    return event.venue_text if shown else None


async def archive_event(
    session: AsyncSession, principal: Principal, event_id: UUID
) -> ArchiveEventOut:
    """Return the archive view of a dossier (404 when the caller may not read it)."""
    read = await load_archive_readable(session, principal, event_id)
    event, own = read.event, read.own
    docs = [
        d
        for d in await session.scalars(
            select(Document)
            .where(Document.event_id == event.id)
            .order_by(Document.kind, Document.updated_at.desc())
        )
        if (
            visibility_readable(principal, event.organization_id, d.visibility)
            if own
            else d.visibility == "shared"
        )
    ]
    visible = (
        readable_clause(principal, event.organization_id) if own else foreign_readable_clause()
    )
    files = await session.scalars(
        select(Attachment)
        .where(Attachment.event_id == event.id, Attachment.retired_at.is_(None), visible)
        .order_by(Attachment.kind, Attachment.created_at.desc())
    )
    category = (
        await session.get(Category, event.primary_category_id)
        if event.primary_category_id
        else None
    )
    fmt = await session.get(Format, event.format_id) if event.format_id else None
    assert event.organization_id is not None
    org = (await organizations(session, {event.organization_id}))[event.organization_id]
    outcome = event.outcome or {}
    attachments = [attachment_out(a) for a in files]
    if not own:
        attachments = [a.model_copy(update={"consent_note": None}) for a in attachments]
    return ArchiveEventOut(
        id=event.id,
        title=event.title,
        summary=event.summary,
        description_md=event.description_md,
        state=event.state,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        all_day=event.all_day,
        organization=org,
        category=CategoryRef.model_validate(category) if category else None,
        format=FormatRef(slug=fmt.slug, title=fmt.title) if fmt else None,
        venue_name=await _venue_name(session, event, own),
        attendance=outcome.get("attendance"),
        documents=[DocumentItem.model_validate(d) for d in docs],
        attachments=attachments,
        own=own,
    )
