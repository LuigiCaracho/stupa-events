"""The 14 transitions T01 to T12 as data (PLAN 4.3, M3 contract 2.2).

`TRANSITIONS` is the single source for the API, the guard list and the tests. T00 (create)
is not an edge of an existing dossier and lives in the event service. The guards of a
transition stand in the order of the guard table (contract 2.3), which is the order of the
`reasons[]`. `decision.decide` evaluates the right, the state, the mandatory note, Four-Eyes
and then these guards.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

from app.modules.events.states import EventState as S
from app.modules.pipeline.guards import (
    Guard,
    attachments_scanned,
    checklist_done,
    checklist_done_followup,
    date_in_future,
    end_estimated,
    ended_more_than,
    facts_valid,
    flyer_date_confirmed,
    followup_older_than,
    has_field,
    howto_verified,
    human_approval,
    image_or_exception,
    location_confirmed,
    long_running,
    no_open_comment_on_hero,
    no_open_duplicate,
    open_comment_required,
    origin_is,
    outcome_set_or_waived,
    publish_at_reached,
    retrospective_filled,
    rights_complete,
    system_only,
    title_clean,
    venue_or_text,
    wall_clock_ok,
)
from app.modules.pipeline.snapshot import Actor, Snapshot

ACTION_FEED_INVALIDATE = "invalidate_feed_cache"
ACTION_ENSURE_DERIVATIVES = "ensure_derivatives"

type Right = Callable[[Snapshot, Actor], bool]


@dataclass(frozen=True, slots=True)
class Transition:
    """One edge of the state machine with its right, its guards and its follow-up.

    Attributes:
        permission: Right held in the organization of the dossier; `None` for the
            worker-only transitions.
        own_only: A role without `event.submit` fires only on its own dossiers.
        alt_right: A second way to hold the right (the proposer withdrawing).
        system: The worker may fire it (without any permission).
        note_required: The request needs a mandatory note.
        four_eyes: The Four-Eyes rule applies (evaluated before the other guards).
        sets: `(column, rule)` pairs written besides `state` and `rev`. Rules: `actor` (the
            firing sub), `null`, `plus_one`, `slug`, `new_rev` (the revision being written),
            `body` (taken from the request), `scheduled` (reset the public status).
        checklist_phase: The checklist phase whose required items the guard `checklistDone`
            reads (`planning` for T02, `followup` for T09).
    """

    id: str
    source: tuple[S, ...]
    target: S
    permission: str | None
    guards: tuple[Guard, ...] = ()
    own_only: bool = False
    alt_right: Right | None = None
    system: bool = False
    note_required: bool = False
    four_eyes: bool = False
    sets: tuple[tuple[str, str], ...] = ()
    actions: tuple[str, ...] = field(default=())
    checklist_phase: str = "planning"


def _may_withdraw(snapshot: Snapshot, actor: Actor) -> bool:
    if snapshot.organization_id is None:
        return snapshot.created_by == actor.sub
    return (
        actor.can("event.edit")
        and snapshot.created_by == actor.sub
        and snapshot.state == S.IDEA.value
    )


_PUBLISH_GUARDS = (
    image_or_exception,
    rights_complete,
    attachments_scanned,
    no_open_duplicate,
    title_clean,
    no_open_comment_on_hero,
    flyer_date_confirmed,
)
_T02_FIELDS = ("title", "summary", "starts_at", "ends_at", "primary_category_id")

TRANSITIONS: Mapping[str, Transition] = {
    t.id: t
    for t in (
        Transition(
            "T01",
            (S.IDEA,),
            S.PLANNING,
            "event.edit",
            (has_field("title", "starts_at", "organization_id"),),
            own_only=True,
        ),
        Transition(
            "T02",
            (S.PLANNING,),
            S.IN_REVIEW,
            "event.submit",
            (
                has_field(*_T02_FIELDS),
                venue_or_text,
                date_in_future,
                facts_valid,
                checklist_done,
                wall_clock_ok,
                end_estimated,
                long_running,
            ),
            sets=(("submitted_by", "actor"),),
        ),
        Transition(
            "T03",
            (S.IN_REVIEW,),
            S.PLANNING,
            "event.approve",
            (open_comment_required,),
            note_required=True,
            sets=(("submitted_by", "null"), ("approved_by", "null")),
        ),
        Transition(
            "T04",
            (S.IN_REVIEW,),
            S.APPROVED,
            "event.approve",
            (
                has_field(*_T02_FIELDS),
                date_in_future,
                image_or_exception,
                rights_complete,
                attachments_scanned,
                no_open_duplicate,
                title_clean,
                no_open_comment_on_hero,
                flyer_date_confirmed,
                location_confirmed,
                wall_clock_ok,
                end_estimated,
                long_running,
            ),
            four_eyes=True,
            sets=(
                ("slug", "slug"),
                ("public_seq", "plus_one"),
                ("approved_by", "actor"),
                ("publish_at", "body"),
            ),
            actions=(ACTION_ENSURE_DERIVATIVES,),
        ),
        Transition(
            "T05",
            (S.APPROVED,),
            S.LIVE,
            "event.approve",
            (
                system_only(date_in_future),
                *_PUBLISH_GUARDS,
                publish_at_reached,
                human_approval,
            ),
            system=True,
            sets=(("published_rev", "new_rev"),),
            actions=(ACTION_FEED_INVALIDATE,),
        ),
        Transition(
            "T06",
            (S.APPROVED,),
            S.IN_REVIEW,
            "event.approve",
            note_required=True,
            sets=(("approved_by", "null"), ("publish_at", "null")),
        ),
        Transition(
            "T07",
            (S.LIVE,),
            S.APPROVED,
            "event.approve",
            note_required=True,
            sets=(
                ("public_seq", "plus_one"),
                ("published_rev", "null"),
                ("publish_at", "null"),
                ("public_status", "scheduled"),
            ),
            actions=(ACTION_FEED_INVALIDATE,),
        ),
        Transition(
            "T08",
            (S.LIVE,),
            S.FOLLOWUP,
            None,
            (ended_more_than(12), origin_is("internal", "mcp")),
            system=True,
            sets=(("published_rev", "null"),),
            actions=(ACTION_FEED_INVALIDATE,),
        ),
        Transition(
            "T08b",
            (S.LIVE,),
            S.ARCHIVED,
            None,
            (ended_more_than(12), origin_is("imported", "legacy")),
            system=True,
            sets=(("published_rev", "null"),),
            actions=(ACTION_FEED_INVALIDATE,),
        ),
        Transition(
            "T09",
            (S.FOLLOWUP,),
            S.ARCHIVED,
            "event.submit",
            (
                checklist_done_followup,
                retrospective_filled,
                outcome_set_or_waived,
                howto_verified,
            ),
            checklist_phase="followup",
            actions=(ACTION_FEED_INVALIDATE,),
        ),
        Transition(
            "T09b",
            (S.FOLLOWUP,),
            S.ARCHIVED,
            None,
            (followup_older_than(30),),
            system=True,
            actions=(ACTION_FEED_INVALIDATE,),
        ),
        Transition(
            "T10",
            (S.ARCHIVED,),
            S.FOLLOWUP,
            "event.restore",
            note_required=True,
            actions=(ACTION_FEED_INVALIDATE,),
        ),
        Transition(
            "T11",
            (S.IDEA, S.PLANNING, S.IN_REVIEW, S.APPROVED),
            S.WITHDRAWN,
            "event.cancel",
            alt_right=_may_withdraw,
            note_required=True,
        ),
        Transition(
            "T12",
            (S.WITHDRAWN,),
            S.IDEA,
            "event.restore",
            sets=(("submitted_by", "null"), ("approved_by", "null"), ("publish_at", "null")),
        ),
    )
}
