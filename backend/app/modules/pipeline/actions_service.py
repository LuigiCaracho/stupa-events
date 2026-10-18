"""Public-status actions of a live event: cancel, postpone and reinstate (contract 2.4).

Each needs a reason (stored in the status event only, never in the audit data or the
feed), raises `public_seq` and invalidates the feed cache. The public reason code and its
short text are what subscribers see.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events.access import guard_snapshot
from app.modules.pipeline.action_base import (
    ActionContext,
    finish,
    future_check,
    prepare,
    require_reason,
)
from app.modules.pipeline.guards import (
    date_in_future,
    flyer_date_confirmed,
    image_or_exception,
    rights_complete,
    title_clean,
)
from app.modules.pipeline.livecheck import enforce_live
from app.modules.pipeline.reasons import blockers, refusal
from app.modules.pipeline.service import Fired
from app.modules.pipeline.transitions import ACTION_FEED_INVALIDATE
from app.shared.errors import ConflictError, FieldError, ForbiddenError, ValidationProblem
from app.shared.timeutil import utcnow

REINSTATE_GUARDS = (
    date_in_future,
    image_or_exception,
    rights_complete,
    title_clean,
    flyer_date_confirmed,
)


PUBLIC_FROM = {
    "cancel": {"scheduled", "postponed"},
    "postpone": {"scheduled"},
    "reinstate": {"cancelled", "postponed"},
}
PUBLIC_TO = {"cancel": "cancelled", "postpone": "postponed", "reinstate": "scheduled"}


def next_public_status(state: str, public_status: str, action: str) -> str | None:
    """Return the public status after `action`, or `None` when it is not defined here."""
    if state != "live" or public_status not in PUBLIC_FROM[action]:
        return None
    return PUBLIC_TO[action]


def _live(ctx: ActionContext, action: str) -> None:
    if next_public_status(ctx.event.state, ctx.event.public_status, action) is None:
        raise ConflictError("The action is not defined in this state.", code="invalid_transition")


def _public_reason(ctx: ActionContext, code: str, text: str | None) -> tuple[str, str | None]:
    clean = (text or "").strip() or None
    if clean is not None and not ctx.actor.can("event.approve"):
        raise ForbiddenError("Missing permission: event.approve")
    return code, clean


async def cancel(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    reason: str | None,
    public_reason_code: str,
    public_reason_text: str | None,
    expected_rev: int | None = None,
) -> Fired:
    """Cancel a live event: the public status becomes `cancelled`, the dossier stays `live`."""
    ctx = await prepare(session, principal, event_id, "event.cancel", expected_rev=expected_rev)
    _live(ctx, "cancel")
    note = require_reason(reason)
    code, text = _public_reason(ctx, public_reason_code, public_reason_text)
    values = {
        "public_status": "cancelled",
        "public_reason_code": code,
        "public_reason_text": text,
        "public_seq": ctx.event.public_seq + 1,
    }
    return await finish(
        session,
        ctx,
        values,
        audit_action=AuditAction.EVENT_CANCEL,
        audit_data={"publicStatus": "cancelled", "publicReasonCode": code},
        status=("cancel", note),
        actions=(ACTION_FEED_INVALIDATE,),
    )


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
    expected_rev: int | None = None,
    now: datetime | None = None,
) -> Fired:
    """Postpone a live event; with a new date the times change and the status stays `postponed`."""
    ctx = await prepare(session, principal, event_id, "event.cancel", expected_rev=expected_rev)
    _live(ctx, "postpone")
    note = require_reason(reason)
    code, text = _public_reason(ctx, public_reason_code, public_reason_text)
    values: dict[str, object] = {
        "public_status": "postponed",
        "public_reason_code": code,
        "public_reason_text": text,
        "public_seq": ctx.event.public_seq + 1,
    }
    if new_ends_at is not None and new_starts_at is None:
        raise ValidationProblem(
            "newEndsAt needs newStartsAt.",
            errors=[FieldError(field="newEndsAt", msg="needs newStartsAt")],
        )
    if new_starts_at is not None:
        if not ctx.actor.can("event.edit_critical_live"):
            raise ForbiddenError("Missing permission: event.edit_critical_live")
        moment = now or utcnow()
        times = _new_times(ctx, new_starts_at, new_ends_at, moment)
        moved = await guard_snapshot(session, ctx.event, ctx.poster, starts_at=new_starts_at)
        enforce_live(replace(moved, **times), ctx.actor, moment)
        values.update(times)
    return await finish(
        session,
        ctx,
        values,
        audit_action=AuditAction.EVENT_POSTPONE,
        audit_data={"publicStatus": "postponed", "publicReasonCode": code},
        field_class="critical" if new_starts_at is not None else "state",
        status=("postpone", note),
        actions=(ACTION_FEED_INVALIDATE,),
    )


def _new_times(
    ctx: ActionContext, starts: datetime, ends: datetime | None, now: datetime
) -> dict[str, object]:
    duration = ctx.event.ends_at - ctx.event.starts_at
    end = ends if ends is not None else starts + duration
    if end < starts:
        raise ValidationProblem(
            "newEndsAt must not be before newStartsAt.",
            errors=[FieldError(field="newEndsAt", msg="before newStartsAt")],
        )
    future_check(end, now)
    return {"starts_at": starts, "ends_at": end, "end_estimated": False}


async def reinstate(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    reason: str | None,
    expected_rev: int | None = None,
    now: datetime | None = None,
) -> Fired:
    """Take back a cancellation or postponement; the publish guards run on the result."""
    ctx = await prepare(session, principal, event_id, "event.approve", expected_rev=expected_rev)
    _live(ctx, "reinstate")
    note = require_reason(reason)
    result = replace(ctx.snapshot, public_status="scheduled")
    moment = now or utcnow()
    reasons = [r for guard in REINSTATE_GUARDS for r in guard(result, ctx.actor, moment)]
    if blockers(reasons):
        raise refusal(reasons)
    values = {
        "public_status": "scheduled",
        "public_reason_code": "none",
        "public_reason_text": None,
        "public_seq": ctx.event.public_seq + 1,
    }
    return await finish(
        session,
        ctx,
        values,
        audit_action=AuditAction.EVENT_REINSTATE,
        audit_data={"publicStatus": "scheduled"},
        status=("reinstate", note),
        actions=(ACTION_FEED_INVALIDATE,),
    )
