"""The four state changes of a dossier: publish, unpublish, archive and restore.

Each is one function over `step.prepare` and `step.finish`: the right comes from
`Principal.has(perm, org_id)`, the state from the row, and the write is the optimistic
`UPDATE ... WHERE state IN (...) AND rev = :rev`. Every change writes a revision, a status
event with the action word as `transition_id`, an audit entry and, where the public view
changes, queues the feed invalidation. `archive_as_system` is the same step for the worker.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import slugs
from app.modules.events.access import poster_of
from app.modules.events.models import Event
from app.modules.events.postcommit import ACTION_ENSURE_DERIVATIVES, ACTION_FEED_INVALIDATE
from app.modules.events.publish import require_complete
from app.modules.events.states import EventState
from app.modules.events.step import SYSTEM_ARCHIVER, Context, Fired, finish, prepare
from app.shared.errors import ConflictError, ForbiddenError

EDITOR_RIGHT = "event.restore"
RESET_PUBLIC = {
    "public_status": "scheduled",
    "public_reason_code": "none",
    "public_reason_text": None,
}


def require_state(event: Event, *states: EventState) -> None:
    """Raise 409 `invalid_state` unless the dossier is in one of `states`."""
    if event.state not in states:
        raise ConflictError("The action is not defined in this state.", code="invalid_state")


def _audit(event: Event, action: str, target: EventState) -> dict[str, Any]:
    return {"action": action, "from": event.state, "to": target.value}


async def publish(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    expected_rev: int | None,
    requires_editor: bool = False,
) -> Fired:
    """Publish a draft: the dossier gets its slug and enters the feed.

    Args:
        session: The open session (no commit).
        principal: The caller.
        event_id: The dossier.
        expected_rev: The version the caller saw.
        requires_editor: Setting `publish_requires_editor`: only the editorial team clicks.

    Raises:
        NotFoundError: No read right.
        ForbiddenError: No `event.publish` in the organization, or the setting binds.
        ConflictError: `invalid_state` outside `draft`, `conflict` on a stale version.
        ValidationProblem: `publish_incomplete` without title, start or organization.
    """
    ctx = await prepare(session, principal, event_id, "event.publish", expected_rev=expected_rev)
    if requires_editor and not principal.has(EDITOR_RIGHT, ctx.event.organization_id):
        raise ForbiddenError("Only the editorial team publishes.")
    event = ctx.event
    require_state(event, EventState.DRAFT)
    require_complete(event)
    slug = event.slug or await slugs.unique_slug(
        session, slugs.base_slug(event.title, event.starts_at, event.tzid)
    )
    values = {
        "state": EventState.PUBLISHED.value,
        "slug": slug,
        "published_at": datetime.now(UTC),
        "public_seq": event.public_seq + 1,
    }
    return await finish(
        session,
        ctx,
        values,
        action="publish",
        audit_action=AuditAction.EVENT_TRANSITION,
        audit_data=_audit(event, "publish", EventState.PUBLISHED),
        actions=(ACTION_ENSURE_DERIVATIVES, ACTION_FEED_INVALIDATE),
        states=(EventState.DRAFT.value,),
    )


async def unpublish(
    session: AsyncSession, principal: Principal, event_id: UUID, *, expected_rev: int | None
) -> Fired:
    """Take a published dossier back to draft; the slug stays, the public status resets."""
    ctx = await prepare(session, principal, event_id, "event.publish", expected_rev=expected_rev)
    event = ctx.event
    require_state(event, EventState.PUBLISHED)
    values = {
        "state": EventState.DRAFT.value,
        "published_at": None,
        "public_seq": event.public_seq + 1,
        **RESET_PUBLIC,
    }
    return await finish(
        session,
        ctx,
        values,
        action="unpublish",
        audit_action=AuditAction.EVENT_TRANSITION,
        audit_data=_audit(event, "unpublish", EventState.DRAFT),
        actions=(ACTION_FEED_INVALIDATE,),
        states=(EventState.PUBLISHED.value,),
    )


def _archive_values(event: Event) -> dict[str, Any]:
    values: dict[str, Any] = {"state": EventState.ARCHIVED.value}
    if event.state == EventState.PUBLISHED:
        values["public_seq"] = event.public_seq + 1
    return values


async def archive(
    session: AsyncSession, principal: Principal, event_id: UUID, *, expected_rev: int | None
) -> Fired:
    """Archive a draft or a published dossier; the documentation stays writable."""
    ctx = await prepare(session, principal, event_id, "event.publish", expected_rev=expected_rev)
    event = ctx.event
    require_state(event, EventState.DRAFT, EventState.PUBLISHED)
    return await finish(
        session,
        ctx,
        _archive_values(event),
        action="archive",
        audit_action=AuditAction.EVENT_TRANSITION,
        audit_data=_audit(event, "archive", EventState.ARCHIVED),
        actions=(ACTION_FEED_INVALIDATE,),
        states=(EventState.DRAFT.value, EventState.PUBLISHED.value),
    )


async def archive_as_system(session: AsyncSession, event: Event) -> Fired:
    """Archive an ended published dossier for the worker (no read scope, system actor).

    Raises:
        ConflictError: `invalid_state` when the dossier is no longer published.
        VersionConflict: The dossier changed in the meantime.
    """
    require_state(event, EventState.PUBLISHED)
    ctx = Context(event, await poster_of(session, event), SYSTEM_ARCHIVER, "system")
    return await finish(
        session,
        ctx,
        _archive_values(event),
        action="archive",
        audit_action=AuditAction.EVENT_TRANSITION,
        audit_data=_audit(event, "archive", EventState.ARCHIVED),
        actions=(ACTION_FEED_INVALIDATE,),
        states=(EventState.PUBLISHED.value,),
    )


async def restore(
    session: AsyncSession, principal: Principal, event_id: UUID, *, expected_rev: int | None
) -> Fired:
    """Bring an archived dossier back as a draft (editorial team); it leaves the feed."""
    ctx = await prepare(session, principal, event_id, "event.restore", expected_rev=expected_rev)
    event = ctx.event
    require_state(event, EventState.ARCHIVED)
    values = {
        "state": EventState.DRAFT.value,
        "published_at": None,
        "public_seq": event.public_seq + 1,
        **RESET_PUBLIC,
    }
    return await finish(
        session,
        ctx,
        values,
        action="restore",
        audit_action=AuditAction.EVENT_TRANSITION,
        audit_data=_audit(event, "restore", EventState.DRAFT),
        actions=(ACTION_FEED_INVALIDATE,),
        states=(EventState.ARCHIVED.value,),
    )
