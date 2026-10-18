"""Image exception (E41): the editors may publish an event without a poster, for one event.

The exception holds for this event id only. It is audited and a revision records it.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import revisions
from app.modules.events.access import load_visible
from app.modules.events.models import Event
from app.modules.events.states import EventState
from app.shared.errors import ConflictError, ForbiddenError
from app.shared.timeutil import utcnow

OPEN_STATES = frozenset(
    {
        EventState.IDEA.value,
        EventState.PLANNING.value,
        EventState.IN_REVIEW.value,
        EventState.APPROVED.value,
    }
)


async def grant_image_exception(
    session: AsyncSession, principal: Principal, event_id: UUID, reason: str
) -> Event:
    """Record the image exception on the event (no commit).

    Raises:
        NotFoundError: No read right on the event.
        ForbiddenError: The principal lacks `event.image_exception`.
        ConflictError: `field_locked` once the event is live, `conflict` on a race.
    """
    event = await load_visible(session, principal, event_id)
    if not principal.has("event.image_exception", event.organization_id):
        raise ForbiddenError("Missing permission: event.image_exception")
    if event.state not in OPEN_STATES:
        raise ConflictError("Field is locked in this state.", code="field_locked")
    grant = {"granted_by": principal.sub, "reason": reason, "at": utcnow().isoformat()}
    result = await session.execute(
        update(Event)
        .where(Event.id == event.id, Event.rev == event.rev)
        .values(image_exception=grant, rev=Event.rev + 1)
        .returning(Event)
        .execution_options(populate_existing=True, synchronize_session=False)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("The dossier was changed in the meantime.")
    await revisions.append_revision(session, updated, actor=principal.sub, field_class="dossier")
    await revisions.audit(
        session, updated, actor=principal.sub, action=AuditAction.EVENT_IMAGE_EXCEPTION
    )
    return updated
