"""Guards of the pipeline as pure functions `(snapshot, actor, now) -> list[Reason]`.

An empty list means the guard holds. The service shows all reasons before the click and
refuses a transition with the first blocker (PLAN 4.4). The fixed order of the codes is
`field_missing`, `start_in_past`, `image_required`, `four_eyes`.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.modules.pipeline.reasons import FixAction, Reason, blocker
from app.modules.pipeline.snapshot import Actor, Snapshot

type Guard = Callable[[Snapshot, Actor, datetime], list[Reason]]

FIELD_NAMES: dict[str, str] = {
    "title": "title",
    "summary": "summary",
    "starts_at": "startsAt",
    "ends_at": "endsAt",
    "organization_id": "organizationId",
    "primary_category_id": "primaryCategoryId",
    "venue_text": "venueText",
}


def _present(value: object) -> bool:
    return bool(value.strip()) if isinstance(value, str) else value is not None


def has_field(*fields: str) -> Guard:
    """Build the guard `hasField`: every named snapshot field is filled."""

    def guard(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
        return [
            blocker("field_missing", field=FIELD_NAMES[name], fix=FixAction.FILL_FIELD)
            for name in fields
            if not _present(getattr(snapshot, name))
        ]

    return guard


def date_in_future(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `dateInFuture`: the event has not ended yet (a running event passes)."""
    if snapshot.ends_at is not None and snapshot.ends_at > now:
        return []
    return [blocker("start_in_past", field="startsAt", fix=FixAction.CHANGE_DATE)]


def image_or_exception(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `imageOrException`: a usable poster or a valid image exception (E41)."""
    if snapshot.image_exception_reason is not None:
        return []
    if snapshot.poster is not None and snapshot.poster.usable:
        return []
    return [blocker("image_required", field="poster", fix=FixAction.UPLOAD_POSTER)]


def four_eyes(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `fourEyes`: a stub in M1. It is wired into T04 and always holds.

    The rule (the approving person did not submit) arrives with M3. `EDITOR_FOUR_EYES`
    will decide whether it binds the editors as well.
    """
    return []


def organization_scope_or_proposal(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `organizationScopeOrProposal` of T00: the actor may create in the organization.

    A proposal without an organization is not part of M1, so a missing organization
    counts as a missing field.
    """
    if snapshot.organization_id is None:
        return [blocker("field_missing", field="organizationId", fix=FixAction.FILL_FIELD)]
    if not actor.can("event.create"):
        return [blocker("organization_scope", field="organizationId")]
    return []
