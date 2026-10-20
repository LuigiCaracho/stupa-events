"""Shared write rules of the dossier tabs: load, permission, own-dossier rule, closed state.

Every write route of attachments, documents, checklist, comments and quotes loads the dossier
through `load_for_write`. An unreadable dossier is a 404 before any permission is looked at;
a role below `event.submit` (the submitter) works on its own dossiers only.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.access import load_visible
from app.modules.events.models import Event
from app.modules.orgs.scope import bind, restricted_to_own
from app.shared.errors import ConflictError, ForbiddenError

CLOSED_STATES = frozenset({"archived", "withdrawn"})


def ensure_open(event: Event) -> None:
    """Refuse a write on a closed dossier (409 `dossier_closed`)."""
    if event.state in CLOSED_STATES:
        raise ConflictError("The dossier is closed.", code="dossier_closed")


def ensure_permission(
    principal: Principal, event: Event, permission: str, *, own_only: bool = True
) -> None:
    """Require `permission` in the organization of the dossier (403 otherwise).

    Args:
        principal: The caller, with bound organization ids.
        event: The dossier.
        permission: A permission of the catalogue.
        own_only: Apply the submitter rule (own dossiers only).
    """
    org_id = event.organization_id
    if org_id is None or not principal.has(permission, org_id):
        raise ForbiddenError(f"Missing permission: {permission}")
    if own_only and restricted_to_own(principal, org_id) and event.created_by != principal.sub:
        raise ForbiddenError("Only the creator may change this dossier.")


async def load_readable(session: AsyncSession, principal: Principal, event_id: UUID) -> Event:
    """Load a dossier the caller reads (404 otherwise) and bind its organization ids."""
    event = await load_visible(session, principal, event_id)
    await bind(session, principal)
    return event


async def load_for_write(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    permission: str,
    *,
    own_only: bool = True,
) -> Event:
    """Load a dossier for a write: 404, then permission, then the closed state."""
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, permission, own_only=own_only)
    ensure_open(event)
    return event
