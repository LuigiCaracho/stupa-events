"""The transition table of M1 as data, and the pure decision function.

`TRANSITIONS` is the single source for the API, the guard list and the tests. T00
(create) is not a transition of an existing dossier and lives in the event service.
`decide` answers in a fixed order: the right, then the state, then the guards.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from app.modules.events.states import EventState
from app.modules.pipeline.guards import (
    Guard,
    date_in_future,
    four_eyes,
    has_field,
    image_or_exception,
)
from app.modules.pipeline.reasons import Reason, blockers
from app.modules.pipeline.snapshot import Actor, Snapshot

ACTION_FEED_INVALIDATE = "invalidate_feed_cache"
ACTION_ENSURE_DERIVATIVES = "ensure_derivatives"


@dataclass(frozen=True, slots=True)
class Transition:
    """One edge of the state machine with its right, its guards and its follow-up."""

    id: str
    source: EventState
    target: EventState
    permission: str
    guards: tuple[Guard, ...]
    own_only: bool = False
    sets: tuple[str, ...] = field(default=())
    actions: tuple[str, ...] = field(default=())


TRANSITIONS: Mapping[str, Transition] = {
    t.id: t
    for t in (
        Transition(
            "T01",
            EventState.IDEA,
            EventState.PLANNING,
            "event.edit",
            (has_field("title", "starts_at", "organization_id"),),
            own_only=True,
        ),
        Transition(
            "T02",
            EventState.PLANNING,
            EventState.IN_REVIEW,
            "event.submit",
            (
                has_field(
                    "title",
                    "summary",
                    "starts_at",
                    "ends_at",
                    "primary_category_id",
                    "venue_text",
                ),
                date_in_future,
            ),
            sets=("submitted_by",),
        ),
        Transition(
            "T04",
            EventState.IN_REVIEW,
            EventState.APPROVED,
            "event.approve",
            (date_in_future, image_or_exception, four_eyes),
            sets=("slug", "public_seq", "approved_by"),
            actions=(ACTION_ENSURE_DERIVATIVES,),
        ),
        Transition(
            "T05",
            EventState.APPROVED,
            EventState.LIVE,
            "event.approve",
            (image_or_exception,),
            actions=(ACTION_FEED_INVALIDATE,),
        ),
    )
}


@dataclass(frozen=True, slots=True)
class Verdict:
    """Result of `decide`: `ok`, or why the transition must not run."""

    outcome: Literal["ok", "forbidden", "invalid_transition", "blocked"]
    reasons: tuple[Reason, ...] = ()


def permitted(transition: Transition, snapshot: Snapshot, actor: Actor) -> bool:
    """Tell if the actor holds the right for this transition on this dossier."""
    if not actor.can(transition.permission):
        return False
    return not (
        transition.own_only and not actor.can("event.submit") and snapshot.created_by != actor.sub
    )


def guard_reasons(
    transition: Transition, snapshot: Snapshot, actor: Actor, now: datetime
) -> list[Reason]:
    """Run all guards of the transition and collect their reasons in guard order."""
    return [reason for guard in transition.guards for reason in guard(snapshot, actor, now)]


def decide(transition: Transition, snapshot: Snapshot, actor: Actor, now: datetime) -> Verdict:
    """Decide whether `actor` may fire `transition` on `snapshot` at `now`.

    Same input, same decision, whatever the caller (REST, worker, factory).
    """
    if not permitted(transition, snapshot, actor):
        return Verdict("forbidden")
    if snapshot.state != transition.source:
        return Verdict("invalid_transition")
    reasons = guard_reasons(transition, snapshot, actor, now)
    return Verdict("blocked" if blockers(reasons) else "ok", tuple(reasons))


def allowed_transitions(snapshot: Snapshot, actor: Actor) -> list[str]:
    """List the transitions the actor can try from the current state (UX hint only)."""
    return [
        t.id
        for t in TRANSITIONS.values()
        if t.source == snapshot.state and permitted(t, snapshot, actor)
    ]
