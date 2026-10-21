"""Enter the outcome of an event: attendance, costs, revenue, notes or the waiver.

Allowed in `live` after the end and in `followup`, by a person with `event.edit` in the
organization (a submitter only on its own dossiers). The write is optimistic on `event.rev`,
records a revision of the class `dossier` and an audit entry with ids only. The outcome is
never public.
"""

from __future__ import annotations

from datetime import datetime
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
from app.shared.errors import ConflictError
from app.shared.timeutil import utcnow

OUTCOME_STATES = frozenset({"live", "followup"})


def ensure_outcome_phase(event: Event, now: datetime) -> None:
    """Refuse the write unless the event is in `followup` or `live` and over (409)."""
    over = event.state == "followup" or (event.state == "live" and event.ends_at <= now)
    if not over:
        raise ConflictError("Field is locked in this state.", code="field_locked")


async def put_outcome(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    body: OutcomeIn,
    expected_rev: int,
    *,
    now: datetime | None = None,
) -> Event:
    """Replace the outcome of a dossier (no commit).

    Raises:
        NotFoundError: No read right.
        ForbiddenError: No `event.edit` in the organization.
        ConflictError: `field_locked` outside `live` (after the end) and `followup`.
        VersionConflict: `expected_rev` is stale.
        ValidationProblem: `waiver_reason_required`.
    """
    event = await load_readable(session, principal, event_id)
    ensure_permission(principal, event, "event.edit")
    ensure_outcome_phase(event, now or utcnow())
    if expected_rev != event.rev:
        raise VersionConflict(event)
    updated = await update_event(session, event, {"outcome": body.stored()}, states=[event.state])
    await revisions.append_revision(session, updated, actor=principal.sub, field_class="dossier")
    await revisions.audit(
        session, updated, actor=principal.sub, action=AuditAction.EVENT_OUTCOME, data={}
    )
    return updated
