"""Confirm that a free venue text is public: the action behind the guard `locationConfirmed`.

A free `venue_text` is shown in the feed and the calendar only after a person with
`event.approve` confirmed its precision (`exact` or `building`, never `hidden`). A change of
the text resets the mark (`EventService`). In `live` the confirmation changes the public
view, so `public_seq` rises and the feed cache is rebuilt.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.pipeline.action_base import finish, prepare
from app.modules.pipeline.allowed import LOCATION_STATES
from app.modules.pipeline.service import Fired
from app.modules.pipeline.transitions import ACTION_FEED_INVALIDATE
from app.shared.errors import ConflictError
from app.shared.timeutil import utcnow

type Precision = Literal["exact", "building"]


async def confirm_location(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    precision: Precision,
    *,
    expected_rev: int | None = None,
) -> Fired:
    """Record the precision of the free venue text and who confirmed it (no commit).

    Raises:
        NotFoundError: No read right.
        ForbiddenError: No `event.approve` in the organization.
        ConflictError: `invalid_transition` without a free venue text or in a closed state.
    """
    ctx = await prepare(session, principal, event_id, "event.approve", expected_rev=expected_rev)
    event = ctx.event
    free_text = event.venue_id is None and bool((event.venue_text or "").strip())
    if event.state not in LOCATION_STATES or not free_text:
        raise ConflictError("The action is not defined in this state.", code="invalid_transition")
    values: dict[str, object] = {
        "location_precision": precision,
        "location_confirmed_at": utcnow(),
        "location_confirmed_by": principal.sub,
    }
    live = event.state == "live"
    if live:
        values["public_seq"] = event.public_seq + 1
    return await finish(
        session,
        ctx,
        values,
        audit_action=AuditAction.EVENT_LOCATION_CONFIRM,
        audit_data={"precision": precision},
        field_class="critical",
        actions=(ACTION_FEED_INVALIDATE,) if live else (),
    )
