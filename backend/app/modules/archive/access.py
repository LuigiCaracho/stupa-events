"""Read access to archived dossiers of other organizations (PLAN 5.4, contract 4.1).

`load_visible` stays strict: a dossier of a foreign organization is a 404. The archive is the
second door: a person with `library.read` reads the core data, the `shared` documents and the
clean `shared` attachments of any *archived* dossier that was once published (`published_at`).
Everything else on a foreign dossier stays a 404. `ArchiveRead.own` tells the two relations apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.models import Event
from app.modules.orgs.scope import bind, readable_org_ids
from app.shared.errors import NotFoundError

ARCHIVE_STATE = "archived"
LISTED_ARCHIVE_SQL = "(e.state = 'archived' AND e.published_at IS NOT NULL)"


@dataclass(frozen=True, slots=True)
class ArchiveRead:
    """A dossier the caller may read and how it relates to the caller's organizations."""

    event: Event
    own: bool


async def is_own(session: AsyncSession, principal: Principal, event: Event) -> bool:
    """Tell if the dossier lies in the reading scope of the principal."""
    scope = await readable_org_ids(session, principal)
    return (
        scope is None
        or event.organization_id in scope
        or (event.organization_id is None and event.created_by == principal.sub)
    )


async def foreign_archived(
    session: AsyncSession, principal: Principal, event_id: UUID
) -> Event | None:
    """Return an archived dossier of another organization for reading, else `None`."""
    event = await session.get(Event, event_id)
    if (
        event is None
        or event.state != ARCHIVE_STATE
        or event.published_at is None
        or event.organization_id is None
        or not principal.has("library.read")
    ):
        return None
    return event


async def load_archive_readable(
    session: AsyncSession, principal: Principal, event_id: UUID
) -> ArchiveRead:
    """Load a dossier for reading: an own one in any state, a foreign one when archived.

    Raises:
        NotFoundError: The dossier does not exist, or it is foreign and not archived.
    """
    event = await session.get(Event, event_id)
    if event is None:
        raise NotFoundError("event not found")
    await bind(session, principal)
    if await is_own(session, principal, event):
        return ArchiveRead(event, True)
    if await foreign_archived(session, principal, event_id) is None:
        raise NotFoundError("event not found")
    return ArchiveRead(event, False)
