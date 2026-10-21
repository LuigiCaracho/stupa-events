"""The public status of a published dossier: cancel, postpone and reinstate.

The dossier stays `published`; only `public_status` and, for a postponement, the times
change. Each action raises `public_seq` and invalidates the feed. The public reason code and
its short text are what subscribers see; the free reason of the request stays in the history.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import allday
from app.modules.events.lifecycle import require_state
from app.modules.events.models import Event
from app.modules.events.postcommit import ACTION_FEED_INVALIDATE
from app.modules.events.states import EventState
from app.modules.events.step import Context, Fired, clean_reason, finish, prepare
from app.shared.errors import ConflictError, FieldError, ValidationProblem
from app.shared.timeutil import utcnow

PUBLIC_FROM = {
    "cancel": {"scheduled", "postponed"},
    "postpone": {"scheduled"},
    "reinstate": {"cancelled", "postponed"},
}
PUBLIC_TO = {"cancel": "cancelled", "postpone": "postponed", "reinstate": "scheduled"}
AUDIT = {
    "cancel": AuditAction.EVENT_CANCEL,
    "postpone": AuditAction.EVENT_POSTPONE,
    "reinstate": AuditAction.EVENT_REINSTATE,
}


def next_public_status(state: str, public_status: str, action: str) -> str | None:
    """Return the public status after `action`, or `None` when it is not defined here."""
    if state != EventState.PUBLISHED or public_status not in PUBLIC_FROM[action]:
        return None
    return PUBLIC_TO[action]


async def _ready(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    action: str,
    expected_rev: int | None,
) -> Context:
    ctx = await prepare(session, principal, event_id, "event.cancel", expected_rev=expected_rev)
    require_state(ctx.event, EventState.PUBLISHED)
    if next_public_status(ctx.event.state, ctx.event.public_status, action) is None:
        raise ConflictError("The action is not defined in this state.", code="invalid_state")
    return ctx


def _values(event: Event, action: str, code: str, text: str | None) -> dict[str, Any]:
    return {
        "public_status": PUBLIC_TO[action],
        "public_reason_code": code,
        "public_reason_text": text,
        "public_seq": event.public_seq + 1,
    }


async def _apply(
    session: AsyncSession,
    ctx: Context,
    action: str,
    values: dict[str, Any],
    reason: str | None,
    code: str,
) -> Fired:
    return await finish(
        session,
        ctx,
        values,
        action=action,
        audit_action=AUDIT[action],
        audit_data={"publicStatus": PUBLIC_TO[action], "publicReasonCode": code},
        note=clean_reason(reason),
        actions=(ACTION_FEED_INVALIDATE,),
        states=(EventState.PUBLISHED.value,),
    )


async def cancel(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    reason: str | None,
    public_reason_code: str,
    public_reason_text: str | None,
    expected_rev: int | None,
) -> Fired:
    """Cancel a published event: the public status becomes `cancelled`."""
    ctx = await _ready(session, principal, event_id, "cancel", expected_rev)
    values = _values(ctx.event, "cancel", public_reason_code, public_reason_text)
    return await _apply(session, ctx, "cancel", values, reason, public_reason_code)


def _new_times(
    event: Event, starts: datetime, ends: datetime | None, now: datetime
) -> dict[str, Any]:
    end = ends if ends is not None else starts + (event.ends_at - event.starts_at)
    if end < starts:
        raise ValidationProblem(
            "newEndsAt must not be before newStartsAt.",
            errors=[FieldError(field="newEndsAt", msg="before newStartsAt")],
        )
    if end <= now:
        raise ValidationProblem(
            "The new date must lie in the future.",
            code="start_in_past",
            errors=[FieldError(field="newStartsAt", msg="must be in the future")],
        )
    times: dict[str, Any] = {"starts_at": starts, "ends_at": end, "end_estimated": False}
    if event.all_day:
        starts_on, ends_on = allday.days_of(starts, end, event.tzid)
        times |= {"starts_on": starts_on, "ends_on": ends_on}
    return times


async def postpone(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    reason: str | None,
    public_reason_code: str,
    public_reason_text: str | None,
    new_starts_at: datetime | None = None,
    new_ends_at: datetime | None = None,
    expected_rev: int | None,
    now: datetime | None = None,
) -> Fired:
    """Postpone a published event; with a new date the times change too."""
    ctx = await _ready(session, principal, event_id, "postpone", expected_rev)
    values = _values(ctx.event, "postpone", public_reason_code, public_reason_text)
    if new_ends_at is not None and new_starts_at is None:
        raise ValidationProblem(
            "newEndsAt needs newStartsAt.",
            errors=[FieldError(field="newEndsAt", msg="needs newStartsAt")],
        )
    if new_starts_at is not None:
        values |= _new_times(ctx.event, new_starts_at, new_ends_at, now or utcnow())
    return await _apply(session, ctx, "postpone", values, reason, public_reason_code)


async def reinstate(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    reason: str | None,
    expected_rev: int | None,
) -> Fired:
    """Take back a cancellation or postponement."""
    ctx = await _ready(session, principal, event_id, "reinstate", expected_rev)
    values = _values(ctx.event, "reinstate", "none", None)
    return await _apply(session, ctx, "reinstate", values, reason, "none")
