"""Read access to dossiers and the helpers around the current poster.

A principal reads the events of the organizations it has a role in; `event.read_all`
reads every event. A person also reads its own draft without an organization (an old
proposal it created before M5b). An event the principal cannot read does not exist for it: 404, no
existence oracle (PLAN 5.1).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.models import Event
from app.modules.files.models import Attachment
from app.modules.orgs.scope import readable_org_ids
from app.shared.errors import NotFoundError


async def load_visible(session: AsyncSession, principal: Principal, event_id: UUID) -> Event:
    """Load an event the principal may read.

    Raises:
        NotFoundError: The event does not exist or the principal may not read it.
    """
    scope = await readable_org_ids(session, principal)
    event = await session.get(Event, event_id)
    if event is None or not (
        scope is None
        or event.organization_id in scope
        or (event.organization_id is None and event.created_by == principal.sub)
    ):
        raise NotFoundError("event not found")
    return event


async def poster_of(session: AsyncSession, event: Event) -> Attachment | None:
    """Return the current poster attachment of the event, if any."""
    if event.hero_attachment_id is None:
        return None
    return await session.get(Attachment, event.hero_attachment_id)


def location_is_confirmed(event: Event) -> bool:
    """Tell if the venue of a dossier is settled: a venue row, no free text, or a confirmed one."""
    return (
        event.venue_id is not None
        or not (event.venue_text or "").strip()
        or (event.location_confirmed_at is not None and event.location_precision != "hidden")
    )


async def visible_events_query(session: AsyncSession, principal: Principal) -> Select[Event]:
    """Return `select(Event)` limited in SQL to the organizations the principal reads."""
    scope = await readable_org_ids(session, principal)
    query = select(Event)
    if scope is None:
        return query
    own_orphan = and_(Event.organization_id.is_(None), Event.created_by == principal.sub)
    return query.where(or_(Event.organization_id.in_(scope), own_orphan))
