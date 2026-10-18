"""The pure decision function of the state machine.

`decide` answers in a fixed order: the right (403), the state (409), the mandatory note
(422), Four-Eyes (403), then the remaining guards (422). The same input gives the same
decision whatever the caller is: REST, worker or factory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.modules.pipeline.guards import four_eyes
from app.modules.pipeline.reasons import Reason, blockers
from app.modules.pipeline.snapshot import Actor, Snapshot
from app.modules.pipeline.transitions import TRANSITIONS, Transition

type Outcome = Literal[
    "ok", "forbidden", "invalid_transition", "reason_required", "four_eyes", "blocked"
]


@dataclass(frozen=True, slots=True)
class Verdict:
    """Result of `decide`: `ok`, or why the transition must not run."""

    outcome: Outcome
    reasons: tuple[Reason, ...] = ()


def permitted(transition: Transition, snapshot: Snapshot, actor: Actor) -> bool:
    """Tell if the actor holds the right for this transition on this dossier."""
    if actor.kind == "system":
        return transition.system
    if transition.permission is None:
        return False
    if actor.can(transition.permission) and not (
        transition.own_only and not actor.can("event.submit") and snapshot.created_by != actor.sub
    ):
        return True
    return transition.alt_right is not None and transition.alt_right(snapshot, actor)


def guard_reasons(
    transition: Transition, snapshot: Snapshot, actor: Actor, now: datetime
) -> list[Reason]:
    """Run all guards of the transition and collect their reasons in guard order."""
    return [reason for guard in transition.guards for reason in guard(snapshot, actor, now)]


def decide(
    transition: Transition,
    snapshot: Snapshot,
    actor: Actor,
    now: datetime,
    *,
    note_given: bool = True,
) -> Verdict:
    """Decide whether `actor` may fire `transition` on `snapshot` at `now`.

    Args:
        transition: The edge to fire.
        snapshot: The dossier as the guards read it.
        actor: Who fires.
        now: The decision time.
        note_given: Whether the request carries a non-empty note. The guard preview
            passes `True`, because the note is not a property of the dossier.
    """
    if not permitted(transition, snapshot, actor):
        return Verdict("forbidden")
    if snapshot.state not in {s.value for s in transition.source}:
        return Verdict("invalid_transition")
    if transition.note_required and not note_given:
        return Verdict("reason_required")
    if transition.four_eyes:
        refusal = four_eyes(snapshot, actor, now)
        if refusal:
            return Verdict("four_eyes", tuple(refusal))
    reasons = guard_reasons(transition, snapshot, actor, now)
    return Verdict("blocked" if blockers(reasons) else "ok", tuple(reasons))


def allowed_transitions(snapshot: Snapshot, actor: Actor) -> list[str]:
    """List the transitions the actor can try from the current state (UX hint only)."""
    return [
        t.id
        for t in TRANSITIONS.values()
        if snapshot.state in {s.value for s in t.source} and permitted(t, snapshot, actor)
    ]
