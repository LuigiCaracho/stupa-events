"""Review markers on a dossier: "seen" for text changes in `live`, and "flyer checked"."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.pipeline.action_base import finish, prepare
from app.modules.pipeline.fieldclass import edit_right
from app.modules.pipeline.service import Fired
from app.shared.errors import ConflictError, ForbiddenError
from app.shared.timeutil import utcnow

FLYER_STATES = ("idea", "planning", "in_review")


async def acknowledge_changes(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    expected_rev: int | None = None,
) -> Fired:
    """Mark the text changes since the publication as seen (`text_reviewed_rev`)."""
    ctx = await prepare(
        session, principal, event_id, "event.edit_critical_live", expected_rev=expected_rev
    )
    if ctx.event.state != "live":
        raise ConflictError("The action is not defined in this state.", code="invalid_transition")
    return await finish(
        session,
        ctx,
        {"text_reviewed_rev": ctx.event.rev + 1},
        audit_action=AuditAction.EVENT_ACK_CHANGES,
        field_class="dossier",
    )


async def confirm_flyer(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    expected_rev: int | None = None,
) -> Fired:
    """Record that the person checked the date on the flyer (guard `flyer_date`)."""
    ctx = await prepare(session, principal, event_id, "event.edit", expected_rev=expected_rev)
    if not edit_right(ctx.snapshot, ctx.actor):
        raise ForbiddenError("Only the creator may confirm the flyer of this dossier.")
    if ctx.event.state not in FLYER_STATES:
        raise ConflictError("The action is not defined in this state.", code="invalid_transition")
    now = utcnow()
    if ctx.poster is not None:
        ctx.poster.flyer_date_confirmed_at = now
        ctx.poster.flyer_date_confirmed_by = principal.sub
    return await finish(
        session,
        ctx,
        {"flyer_checked_at": now},
        audit_action=AuditAction.EVENT_FLYER_CONFIRM,
        field_class="dossier",
    )
