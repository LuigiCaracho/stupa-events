"""Image exception (E41): the editors may publish an event without a poster, for one event.

The exception holds for this event id only. It is audited and a revision records it.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events.states import EventState
from app.modules.pipeline.action_base import finish, prepare
from app.modules.pipeline.service import Fired
from app.shared.errors import ConflictError
from app.shared.timeutil import utcnow

OPEN_STATES = (
    EventState.IDEA.value,
    EventState.PLANNING.value,
    EventState.IN_REVIEW.value,
    EventState.APPROVED.value,
)


async def grant_image_exception(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    reason: str,
    *,
    expected_rev: int | None = None,
) -> Fired:
    """Record the image exception on the event (no commit).

    Raises:
        NotFoundError: No read right on the event.
        ForbiddenError: The principal lacks `event.image_exception`.
        ConflictError: `field_locked` once the event is live, `conflict` on a race.
    """
    ctx = await prepare(
        session, principal, event_id, "event.image_exception", expected_rev=expected_rev
    )
    if ctx.event.state not in OPEN_STATES:
        raise ConflictError("Field is locked in this state.", code="field_locked")
    grant = {"granted_by": principal.sub, "reason": reason, "at": utcnow().isoformat()}
    fired = await finish(
        session,
        ctx,
        {"image_exception": grant},
        audit_action=AuditAction.EVENT_IMAGE_EXCEPTION,
        field_class="dossier",
        states=OPEN_STATES,
    )
    return fired
