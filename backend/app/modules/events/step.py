"""Shared steps of the lifecycle actions: load and check, then write history, audit and mails.

`prepare` loads the dossier (404 without a read right), checks the version (409 `conflict`)
and the right in the organization of the dossier (403). `finish` writes the change with the
optimistic `UPDATE`, the revision, the status event and the audit entry in the open
transaction. Nothing commits here; the router commits and then runs the post-commit actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import revisions
from app.modules.events.access import load_visible, poster_of
from app.modules.events.conflict import VersionConflict
from app.modules.events.models import Event
from app.modules.events.notices import notice_for
from app.modules.events.postcommit import Committed
from app.modules.events.writer import update_event
from app.modules.files.models import Attachment
from app.modules.notifications.service import PendingMail
from app.modules.orgs.scope import bind
from app.shared.errors import FieldError, ForbiddenError, ValidationProblem

MAX_REASON = 500
SYSTEM_ARCHIVER = "system:archive_ended"


@dataclass(frozen=True, slots=True)
class Fired:
    """Result of a lifecycle action: the changed event and what runs after the commit."""

    event: Event
    actions: tuple[str, ...]
    committed: Committed
    mails: tuple[PendingMail, ...] = ()


@dataclass(frozen=True, slots=True)
class Context:
    """The dossier, its poster and the acting person (or the system) before a change."""

    event: Event
    poster: Attachment | None
    actor: str
    actor_type: str = "human"


async def prepare(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    permission: str,
    *,
    expected_rev: int | None = None,
) -> Context:
    """Load the dossier, check the version and the right.

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
    return Context(event, await poster_of(session, event), principal.sub)


def clean_reason(value: str | None) -> str | None:
    """Return the stripped reason, `None` when empty.

    Raises:
        ValidationProblem: The reason is longer than `MAX_REASON`.
    """
    text = (value or "").strip()
    if len(text) > MAX_REASON:
        raise ValidationProblem(
            "The reason is too long.", errors=[FieldError(field="reason", msg="too long")]
        )
    return text or None


def committed_of(event: Event, poster: Attachment | None) -> Committed:
    """Describe a committed change for the post-commit actions."""
    return Committed(
        event_id=event.id,
        rev=event.rev,
        poster_id=poster.id if poster else None,
        poster_has_derivatives=bool(poster and poster.derivatives),
    )


async def finish(
    session: AsyncSession,
    ctx: Context,
    values: dict[str, Any],
    *,
    audit_action: AuditAction,
    action: str | None = None,
    audit_data: dict[str, Any] | None = None,
    note: str | None = None,
    revision_note: str | None = None,
    actions: tuple[str, ...] = (),
    states: tuple[str, ...] | None = None,
) -> Fired:
    """Write the change, its revision, the status event, the audit entry and the notices.

    Args:
        session: The open session (no commit).
        ctx: The context from `prepare`.
        values: Columns to set.
        audit_action: The audited action.
        action: The lifecycle action word, stored as `transition_id` of the status event;
            `None` for a change that is no state change (no status event, no notice).
        audit_data: Ids and metadata only, never free text.
        note: The free reason, stored in the status event only.
        revision_note: The change note of the revision.
        actions: Names of the follow-up actions after the commit.
        states: States the row must still be in.

    Raises:
        VersionConflict: The row changed in the meantime.
    """
    from_state = ctx.event.state
    updated = await update_event(session, ctx.event, values, states=states)
    await revisions.append_revision(
        session, updated, actor=ctx.actor, actor_type=ctx.actor_type, note=revision_note
    )
    if action is not None:
        await revisions.append_status(
            session,
            updated,
            transition_id=action,
            from_state=from_state,
            actor=ctx.actor,
            actor_type=ctx.actor_type,
            note=note,
        )
    await revisions.audit(session, updated, actor=ctx.actor, action=audit_action, data=audit_data)
    mails = await notice_for(session, updated, action, ctx.actor) if action else ()
    return Fired(updated, actions, committed_of(updated, ctx.poster), mails)
