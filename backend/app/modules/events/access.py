"""Read access to dossiers and the helpers that build a snapshot of one.

A principal reads the events of the organizations it has a role in; `event.read_all`
reads every event. An event the principal cannot read does not exist for it: 404, no
existence oracle (PLAN 5.1).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.models import Event
from app.modules.files.models import Attachment
from app.modules.orgs.scope import readable_org_ids
from app.modules.pipeline.snapshot import PosterSnapshot, Snapshot
from app.shared.errors import NotFoundError


async def load_visible(session: AsyncSession, principal: Principal, event_id: UUID) -> Event:
    """Load an event the principal may read.

    Raises:
        NotFoundError: The event does not exist or the principal may not read it.
    """
    scope = await readable_org_ids(session, principal)
    event = await session.get(Event, event_id)
    if event is None or (scope is not None and event.organization_id not in scope):
        raise NotFoundError("event not found")
    return event


async def poster_of(session: AsyncSession, event: Event) -> Attachment | None:
    """Return the current poster attachment of the event, if any."""
    if event.hero_attachment_id is None:
        return None
    return await session.get(Attachment, event.hero_attachment_id)


def poster_snapshot(poster: Attachment | None) -> PosterSnapshot | None:
    """Reduce a poster row to the facts the guards read."""
    if poster is None or poster.retired_at is not None:
        return None
    return PosterSnapshot(
        scan_status=poster.scan_status,
        has_derivatives=bool(poster.derivatives),
        alt_text=poster.alt_text,
        credit=poster.credit,
        rights_basis=poster.rights_basis,
    )


def valid_exception_reason(event: Event) -> str | None:
    """Return the reason of a valid image exception (at least 10 characters), else None."""
    reason = ((event.image_exception or {}).get("reason") or "").strip()
    return reason if len(reason) >= 10 else None


def snapshot_of(event: Event, poster: Attachment | None) -> Snapshot:
    """Build the guard snapshot of an event and its current poster."""
    return Snapshot(
        state=event.state,
        title=event.title,
        summary=event.summary,
        starts_at=event.starts_at,
        ends_at=event.ends_at,
        organization_id=event.organization_id,
        primary_category_id=event.primary_category_id,
        venue_text=event.venue_text,
        created_by=event.created_by,
        submitted_by=event.submitted_by,
        poster=poster_snapshot(poster),
        image_exception_reason=valid_exception_reason(event),
    )


async def visible_events_query(session: AsyncSession, principal: Principal) -> Select[Event]:
    """Return `select(Event)` limited in SQL to the organizations the principal reads."""
    scope = await readable_org_ids(session, principal)
    query = select(Event)
    return query if scope is None else query.where(Event.organization_id.in_(scope))
