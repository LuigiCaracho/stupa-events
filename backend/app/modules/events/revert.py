"""Put a dossier back to the content of an earlier revision (a function of the history).

The old content runs through the same derivations as a `PATCH` (all-day days, the location
mark, the facts), so the result is as consistent as if a person had typed it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.events import allday
from app.modules.events.editing import bumps_public_seq, has_edit_right, locked_problem
from app.modules.events.models import EventRevision
from app.modules.events.postcommit import ACTION_FEED_INVALIDATE
from app.modules.events.service import derived_values, effective_changes
from app.modules.events.states import EventState
from app.modules.events.step import Fired, finish, prepare
from app.shared.errors import ConflictError, ForbiddenError, NotFoundError

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
) -> Fired:
    """Write a new revision with the content of revision `rev` (no commit).

    Raises:
        NotFoundError: No read right, or the revision does not belong to this dossier.
        ForbiddenError: The principal may not edit this dossier.
        ConflictError: `revert_poster_replaced`, `revert_allday_changed`, `field_locked` in
            the archive.
        VersionConflict: `expected_rev` is stale.
    """
    ctx = await prepare(session, principal, event_id, "event.edit", expected_rev=expected_rev)
    event = ctx.event
    if not has_edit_right(principal, event):
        raise ForbiddenError("Missing permission to edit this dossier")
    if event.state == EventState.ARCHIVED:
        raise locked_problem(("revision",))
    target = await session.scalar(
        select(EventRevision).where(EventRevision.event_id == event.id, EventRevision.rev == rev)
    )
    if target is None:
        raise NotFoundError("revision not found")
    hero = event.hero_attachment_id
    if target.snapshot.get("hero_attachment_id") != (str(hero) if hero else None):
        raise ConflictError(
            "The poster of the old version was replaced.", code="revert_poster_replaced"
        )
    if bool(target.snapshot.get("all_day")) != event.all_day:
        raise ConflictError(
            "The old version differs in all-day mode.", code="revert_allday_changed"
        )
    changes = effective_changes(event, content_of(target.snapshot))
    values: dict[str, Any] = dict(changes)
    values |= await derived_values(session, event, changes)
    if TIME_FIELDS & changes.keys():
        values["end_estimated"] = False
        if event.all_day:
            starts_on, ends_on = allday.days_of(
                changes.get("starts_at", event.starts_at),
                changes.get("ends_at", event.ends_at),
                event.tzid,
            )
            values |= {"starts_on": starts_on, "ends_on": ends_on}
    if bumps_public_seq(event, changes):
        values["public_seq"] = event.public_seq + 1
    return await finish(
        session,
        ctx,
        values,
        audit_action=AuditAction.EVENT_REVERT,
        audit_data={"toRev": rev},
        revision_note=(note or "").strip() or f"Zurückgesetzt auf Revision {rev}",
        actions=(ACTION_FEED_INVALIDATE,) if event.state == EventState.PUBLISHED else (),
    )
