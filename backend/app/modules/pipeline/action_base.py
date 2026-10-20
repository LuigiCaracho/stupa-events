"""Shared steps of the dossier actions: prepare the context, finish with history and audit."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import revisions
from app.modules.events.access import guard_snapshot, load_visible, poster_of
from app.modules.events.conflict import VersionConflict
from app.modules.events.models import Event
from app.modules.events.writer import update_event
from app.modules.files.models import Attachment
from app.modules.orgs.scope import bind
from app.modules.pipeline.actions import Committed
from app.modules.pipeline.actor import actor_of
from app.modules.pipeline.notices import notice_for
from app.modules.pipeline.service import Fired
from app.modules.pipeline.snapshot import Actor, Snapshot
from app.shared.errors import FieldError, ForbiddenError, ValidationProblem

MAX_REASON = 500


@dataclass(frozen=True, slots=True)
class ActionContext:
    """Everything an action reads before it decides."""

    event: Event
    poster: Attachment | None
    snapshot: Snapshot
    actor: Actor
    principal: Principal


async def prepare(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    permission: str,
    *,
    expected_rev: int | None = None,
    editor_four_eyes: bool | None = None,
) -> ActionContext:
    """Load the dossier, check the version and the right (404, 409 `conflict`, 403).

    Raises:
        NotFoundError: No read right.
        VersionConflict: `expected_rev` is stale.
        ForbiddenError: The principal lacks `permission` in the organization.
    """
    event = await load_visible(session, principal, event_id)
    await bind(session, principal)
    if expected_rev is not None and expected_rev != event.rev:
        raise VersionConflict(event)
    if not principal.has(permission, event.organization_id):
        raise ForbiddenError(f"Missing permission: {permission}")
    poster = await poster_of(session, event)
    snapshot = await guard_snapshot(session, event, poster)
    actor = actor_of(principal, event.organization_id, editor_four_eyes)
    return ActionContext(event, poster, snapshot, actor, principal)


def require_reason(value: str | None, *, minimum: int = 1) -> str:
    """Return the stripped reason.

    Raises:
        ValidationProblem: `reason_required` when it is empty or shorter than `minimum`.
    """
    text = (value or "").strip()
    if len(text) < minimum or len(text) > MAX_REASON:
        raise ValidationProblem(
            "A reason is required.",
            code="reason_required",
            errors=[FieldError(field="reason", msg="required")],
        )
    return text


async def finish(
    session: AsyncSession,
    ctx: ActionContext,
    values: dict[str, Any],
    *,
    audit_action: AuditAction,
    audit_data: dict[str, Any] | None = None,
    field_class: str = "state",
    revision_note: str | None = None,
    status: tuple[str, str] | None = None,
    actions: tuple[str, ...] = (),
    states: tuple[str, ...] | None = None,
) -> Fired:
    """Write the change, its revision, an optional status event and the audit entry.

    Args:
        session: The open session (no commit).
        ctx: The context from `prepare`.
        values: Columns to set.
        audit_action: The audited action.
        audit_data: Ids and metadata only, never free text.
        field_class: Class of the revision.
        revision_note: The change note of the revision.
        status: `(transition_id, note)` of the status event, or `None` for none.
        actions: Names of the follow-up actions after the commit.
        states: States the row must still be in.
    """
    updated = await update_event(session, ctx.event, values, states=states)
    actor = ctx.principal.sub
    await revisions.append_revision(
        session, updated, actor=actor, field_class=field_class, note=revision_note
    )
    if status is not None:
        await revisions.append_status(
            session,
            updated,
            transition_id=status[0],
            from_state=ctx.event.state,
            actor=actor,
            note=status[1],
            four_eyes=False,
            submitted_by=ctx.event.submitted_by,
        )
    await revisions.audit(session, updated, actor=actor, action=audit_action, data=audit_data)
    poster = ctx.poster
    mails = await notice_for(session, updated, status[0], actor) if status else ()
    return Fired(
        updated,
        actions,
        Committed(
            event_id=updated.id,
            rev=updated.rev,
            poster_id=poster.id if poster else None,
            poster_has_derivatives=bool(poster and poster.derivatives),
        ),
        mails,
    )


def future_check(ends_at: datetime, now: datetime) -> None:
    """Raise `start_in_past` when an event would end before `now`."""
    if ends_at <= now:
        raise ValidationProblem(
            "The new date must lie in the future.",
            code="start_in_past",
            errors=[FieldError(field="newStartsAt", msg="must be in the future")],
        )
