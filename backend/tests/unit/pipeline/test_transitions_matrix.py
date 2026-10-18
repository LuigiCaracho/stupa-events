"""Truth table of the M1 transitions: state x transition x role x image x clock."""

from __future__ import annotations

from datetime import timedelta
from itertools import product

import pytest

from app.modules.events.states import EventState
from app.modules.pipeline.snapshot import PosterSnapshot
from app.modules.pipeline.transitions import TRANSITIONS, allowed_transitions, decide
from tests.unit.pipeline.support import GOOD_POSTER, NOW, actor, snap

STATES = [s.value for s in EventState]
ROLES = ["viewer", "submitter", "organizer", "approver", "editor"]
NEEDS = {"T01": "event.edit", "T02": "event.submit", "T04": "event.approve", "T05": "event.approve"}
SOURCE = {"T01": "idea", "T02": "planning", "T04": "in_review", "T05": "approved"}


def expected(tid: str, state: str, role: str, creator: bool, poster: bool, future: bool) -> str:
    from app.shared.permissions import ROLE_PERMISSIONS

    perms = ROLE_PERMISSIONS[role]
    if NEEDS[tid] not in perms:
        return "forbidden"
    if tid == "T01" and "event.submit" not in perms and not creator:
        return "forbidden"
    if state != SOURCE[tid]:
        return "invalid_transition"
    if (tid in {"T02", "T04"} and not future) or (tid in {"T04", "T05"} and not poster):
        return "blocked"
    return "ok"


@pytest.mark.parametrize(
    ("tid", "state", "role", "creator", "poster", "future"),
    list(product(NEEDS, STATES, ROLES, [True, False], [True, False], [True, False])),
)
def test_decision_matrix(
    tid: str, state: str, role: str, creator: bool, poster: bool, future: bool
) -> None:
    snapshot = snap(
        state=state,
        created_by="me" if creator else "other",
        poster=GOOD_POSTER if poster else None,
        ends_at=NOW + (timedelta(hours=1) if future else -timedelta(hours=1)),
        starts_at=NOW - timedelta(hours=2) if not future else NOW + timedelta(hours=1),
    )
    verdict = decide(TRANSITIONS[tid], snapshot, actor(role, sub="me"), NOW)
    want = expected(tid, state, role, creator, poster, future)
    assert verdict.outcome == want


def test_t01_blocks_on_missing_required_fields() -> None:
    verdict = decide(TRANSITIONS["T01"], snap(state="idea", title=None), actor("organizer"), NOW)
    assert verdict.outcome == "blocked" and verdict.reasons[0].field == "title"


def test_t02_lists_all_missing_fields_and_the_first_blocker_comes_first() -> None:
    verdict = decide(
        TRANSITIONS["T02"], snap(summary=None, venue_text=None), actor("organizer"), NOW
    )
    assert [r.field for r in verdict.reasons] == ["summary", "venueText"]


def test_t04_reports_past_start_before_missing_image() -> None:
    snapshot = snap(state="in_review", poster=None, ends_at=NOW - timedelta(hours=1))
    verdict = decide(TRANSITIONS["T04"], snapshot, actor("editor"), NOW)
    assert [r.code for r in verdict.reasons] == ["start_in_past", "image_required"]


def test_pending_poster_blocks_t05_too() -> None:
    pending = PosterSnapshot("pending", False, "a", "c", "own_work")
    verdict = decide(
        TRANSITIONS["T05"], snap(state="approved", poster=pending), actor("editor"), NOW
    )
    assert verdict.outcome == "blocked" and verdict.reasons[0].code == "image_required"


def test_same_input_same_decision() -> None:
    snapshot, who = snap(state="in_review"), actor("approver")
    assert decide(TRANSITIONS["T04"], snapshot, who, NOW) == decide(
        TRANSITIONS["T04"], snapshot, who, NOW
    )


@pytest.mark.parametrize(
    ("state", "role", "creator", "want"),
    [
        ("idea", "submitter", True, ["T01"]),
        ("idea", "submitter", False, []),
        ("idea", "organizer", False, ["T01"]),
        ("planning", "organizer", False, ["T02"]),
        ("planning", "submitter", True, []),
        ("in_review", "approver", False, ["T04"]),
        ("in_review", "organizer", False, []),
        ("approved", "editor", False, ["T05"]),
        ("live", "editor", False, []),
        ("idea", "viewer", True, []),
    ],
)
def test_allowed_transitions_hint(state: str, role: str, creator: bool, want: list[str]) -> None:
    snapshot = snap(state=state, created_by="me" if creator else "other")
    assert allowed_transitions(snapshot, actor(role, sub="me")) == want


def test_every_transition_declares_known_states_and_rights() -> None:
    assert set(TRANSITIONS) == set(NEEDS)
    assert all(t.source != t.target for t in TRANSITIONS.values())
