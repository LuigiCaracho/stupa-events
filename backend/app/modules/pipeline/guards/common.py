"""Shared types of the guard package: the `Guard` signature and the system-only wrapper."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from app.modules.pipeline.reasons import Reason
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


def system_only(guard: Guard) -> Guard:
    """Wrap a guard so that it binds the worker only; a human passes it."""

    def wrapped(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
        return guard(snapshot, actor, now) if actor.kind == "system" else []

    wrapped.__doc__ = guard.__doc__
    return wrapped
