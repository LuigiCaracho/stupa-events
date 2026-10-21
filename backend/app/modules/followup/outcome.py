"""Enter the outcome of an event: attendance, costs, revenue, notes or the waiver.

Voluntary and allowed in every state, the archive included, by a person with `event.edit`
in the organization (a submitter only on its own dossiers). The write is optimistic on
`event.rev`, records a revision and an audit entry with ids only. The outcome is never public.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.dossier.rules import ensure_permission, load_readable
from app.modules.events import revisions
from app.modules.events.conflict import VersionConflict
from app.modules.events.models import Event
from app.modules.events.writer import update_event
from app.modules.followup.schemas import OutcomeIn


async def put_outcome(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    body: OutcomeIn,
    expected_rev: int,
) -> Event:
    """Replace the outcome of a dossier (no commit).

    Raises:
        NotFoundError: No read right.
        ForbiddenError: No `event.edit` in the organization.
        VersionConflict: `expected_rev` is stale.
    """
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, "event.edit")
    if expected_rev != event.rev:
        raise VersionConflict(event)
    updated = await update_event(session, event, {"outcome": body.stored()}, states=[event.state])
    await revisions.append_revision(session, updated, actor=principal.sub)
    await revisions.audit(
        session, updated, actor=principal.sub, action=AuditAction.EVENT_OUTCOME, data={}
    )
    return updated
