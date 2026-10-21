"""Put a dossier back to the content of an earlier revision (contract 4.4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import allday
from app.modules.events.access import guard_snapshot
from app.modules.events.models import EventRevision
from app.modules.events.service import derived_values, locked_problem
from app.modules.pipeline.action_base import finish, prepare
from app.modules.pipeline.fieldclass import plan_patch
from app.modules.pipeline.livecheck import enforce_live
from app.modules.pipeline.service import Fired
from app.modules.pipeline.transitions import ACTION_FEED_INVALIDATE
from app.shared.errors import ConflictError, NotFoundError
from app.shared.timeutil import utcnow

CONTENT_FIELDS = (
    "title",
    "summary",
    "description_md",
    "starts_at",
    "ends_at",
    "venue_id",
    "venue_text",
    "primary_category_id",
    "ticket_url",
    "website_url",
    "cost_text",
)
REVERTIBLE = ("idea", "planning", "live")
_TIMES = ("starts_at", "ends_at")
TIME_FIELDS = frozenset(_TIMES)
_IDS = ("venue_id", "primary_category_id")


def content_of(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Read the content fields out of a revision snapshot (missing keys count as empty)."""
    content: dict[str, Any] = {}
    for name in CONTENT_FIELDS:
        value = snapshot.get(name)
        if value is not None and name in _TIMES:
            value = datetime.fromisoformat(value)
        elif value is not None and name in _IDS:
            value = UUID(value)
        content[name] = value
    return content


async def revert_revision(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    rev: int,
    note: str | None = None,
    expected_rev: int | None = None,
    now: datetime | None = None,
) -> Fired:
    """Write a new revision with the content of revision `rev` (no commit).

    Raises:
        NotFoundError: No read right, or the revision does not belong to this dossier.
        ForbiddenError: The principal lacks `event.edit_critical_live`.
        ConflictError: `revert_poster_replaced`, `field_locked` in a closed state.
        ValidationProblem: The live guards refuse the result.
    """
    ctx = await prepare(
        session, principal, event_id, "event.edit_critical_live", expected_rev=expected_rev
    )
    if ctx.event.state not in REVERTIBLE:
        raise ConflictError("Field is locked in this state.", code="field_locked")
    target = await session.scalar(
        select(EventRevision).where(
            EventRevision.event_id == ctx.event.id, EventRevision.rev == rev
        )
    )
    if target is None:
        raise NotFoundError("revision not found")
    hero = ctx.event.hero_attachment_id
    if target.snapshot.get("hero_attachment_id") != (str(hero) if hero else None):
        raise ConflictError(
            "The poster of the old version was replaced.", code="revert_poster_replaced"
        )
    if bool(target.snapshot.get("all_day")) != ctx.event.all_day:
        raise ConflictError(
            "The old version differs in all-day mode.", code="revert_allday_changed"
        )
    plan = plan_patch(ctx.snapshot, ctx.actor, content_of(target.snapshot))
    if plan.locked:
        raise locked_problem(plan.locked)
    if ctx.event.state == "live":
        moved = await guard_snapshot(
            session, ctx.event, ctx.poster, starts_at=plan.changes.get("starts_at")
        )
        enforce_live(replace(moved, **plan.changes), ctx.actor, now or utcnow())
    values: dict[str, Any] = dict(plan.changes)
    values |= await derived_values(session, ctx.event, plan.changes)
    if TIME_FIELDS & values.keys():
        values["end_estimated"] = False
    if ctx.event.all_day and TIME_FIELDS & values.keys():
        starts_on, ends_on = allday.days_of(
            values.get("starts_at", ctx.event.starts_at),
            values.get("ends_at", ctx.event.ends_at),
            ctx.event.tzid,
        )
        values |= {"starts_on": starts_on, "ends_on": ends_on}
    if plan.bump_public_seq:
        values["public_seq"] = ctx.event.public_seq + 1
    return await finish(
        session,
        ctx,
        values,
        audit_action=AuditAction.EVENT_REVERT,
        audit_data={"toRev": rev},
        field_class=plan.field_class,
        revision_note=(note or "").strip() or f"Zurückgesetzt auf Revision {rev}",
        actions=(ACTION_FEED_INVALIDATE,) if ctx.event.state == "live" else (),
    )
