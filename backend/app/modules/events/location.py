"""Confirm that a free venue text is public: the action behind the hint `location_unconfirmed`.

A free `venue_text` is shown in the feed and the calendar only after a person with
`event.publish` confirmed its precision (`exact` or `building`, never `hidden`). A change of
the text resets the mark (`EventService`). In `published` the confirmation changes the public
view, so `public_seq` rises and the feed cache is rebuilt.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events.allowed import LOCATION_STATES
from app.modules.events.postcommit import ACTION_FEED_INVALIDATE
from app.modules.events.states import EventState
from app.modules.events.step import Fired, finish, prepare
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
        ForbiddenError: No `event.publish` in the organization.
        ConflictError: `invalid_state` without a free venue text or in the archive.
    """
    ctx = await prepare(session, principal, event_id, "event.publish", expected_rev=expected_rev)
    event = ctx.event
    free_text = event.venue_id is None and bool((event.venue_text or "").strip())
    if event.state not in LOCATION_STATES or not free_text:
        raise ConflictError("The action is not defined in this state.", code="invalid_state")
    values: dict[str, object] = {
        "location_precision": precision,
        "location_confirmed_at": utcnow(),
        "location_confirmed_by": principal.sub,
    }
    live = event.state == EventState.PUBLISHED
    if live:
        values["public_seq"] = event.public_seq + 1
    return await finish(
        session,
        ctx,
        values,
        audit_action=AuditAction.EVENT_LOCATION_CONFIRM,
        audit_data={"precision": precision},
        actions=(ACTION_FEED_INVALIDATE,) if live else (),
    )
