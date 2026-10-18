"""Full decision matrix: state x transition x actor x image x Four-Eyes x clock x note.

The expectation comes from `oracle.py`, which does not import `TRANSITIONS`. One test per
transition walks its whole product and reports every deviation at once.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from itertools import product

import pytest

from app.modules.events.states import EventState
from app.modules.pipeline.decision import allowed_transitions, decide
from app.modules.pipeline.transitions import TRANSITIONS
from tests.unit.pipeline import oracle
from tests.unit.pipeline.support import GOOD_POSTER, NOW, actor, snap

STATES = [s.value for s in EventState]
POSTERS = ("valid", "missing", "exception")
EYES = ("self", "other", "none")
CLOCKS = ("running", "past")


def snapshot_for(tid: str, state: str, who: str, poster: str, eyes: str, clock: str):  # noqa: ANN201
    starts, ends = (
        (NOW - timedelta(hours=1), NOW + timedelta(hours=2))
        if clock == "running"
        else (NOW - timedelta(days=60), NOW - timedelta(days=60) + timedelta(hours=3))
    )
    submitter = {"self": "me", "other": "someone-else", "none": None}[eyes]
    return snap(
        state=state,
        starts_at=starts,
        ends_at=ends,
        created_by="me" if who == "submitter_own" else "creator",
        submitted_by=submitter,
        approved_by="human-approver",
        publish_at=NOW - timedelta(minutes=5),
        poster=GOOD_POSTER if poster == "valid" else None,
        image_exception_reason="Hochschulveranstaltung" if poster == "exception" else None,
        origin_kind="imported" if tid == "T08b" else "internal",
        entered_followup_at=NOW - timedelta(days=31),
    )


def actor_for(who: str):  # noqa: ANN201
    role = {"submitter_own": "submitter", "submitter_foreign": "submitter"}.get(who, who)
    return actor(role, sub="me")


@pytest.mark.parametrize("tid", sorted(TRANSITIONS))
def test_every_cell_of_the_matrix_matches_the_oracle(tid: str) -> None:
    deviations = []
    for state, who, poster, eyes, clock, note in product(
        STATES, oracle.WHO, POSTERS, EYES, CLOCKS, (True, False)
    ):
        snapshot = snapshot_for(tid, state, who, poster, eyes, clock)
        got = decide(TRANSITIONS[tid], snapshot, actor_for(who), NOW, note_given=note).outcome
        want = oracle.expected(tid, state, who, poster, eyes, clock, note)
        if got != want:
            deviations.append((state, who, poster, eyes, clock, note, got, want))
    assert not deviations, f"{tid}: {len(deviations)} deviations, first: {deviations[:5]}"


def test_table_and_oracle_agree_on_ids_edges_and_rights() -> None:
    assert set(TRANSITIONS) == set(oracle.SOURCES)
    for tid, (sources, target) in oracle.SOURCES.items():
        transition = TRANSITIONS[tid]
        assert {s.value for s in transition.source} == sources, tid
        assert transition.target.value == target, tid
        assert transition.note_required == (tid in oracle.NOTE_REQUIRED), tid
        assert transition.four_eyes == (tid == "T04"), tid


def test_the_sys_only_transitions_have_no_permission_and_humans_never_fire_them() -> None:
    sys_only = {tid for tid, t in TRANSITIONS.items() if t.permission is None}
    assert sys_only == {"T08", "T08b", "T09b"}
    for tid in sys_only:
        for who in ("editor", "admin"):
            snapshot = snapshot_for(
                tid, "live" if tid != "T09b" else "followup", who, "valid", "other", "past"
            )
            assert decide(TRANSITIONS[tid], snapshot, actor_for(who), NOW).outcome == "forbidden"


def test_a_proposal_may_be_withdrawn_by_its_creator_only() -> None:
    proposal = snap(state="idea", organization_id=None, created_by="me")
    holder = actor("member", sub="me")
    assert decide(TRANSITIONS["T11"], proposal, holder, NOW).outcome == "ok"
    other = actor("member", sub="you")
    assert decide(TRANSITIONS["T11"], proposal, other, NOW).outcome == "forbidden"
    assert decide(TRANSITIONS["T11"], proposal, holder, NOW, note_given=False).outcome == (
        "reason_required"
    )
    assert allowed_transitions(proposal, holder) == ["T11"]
    assert decide(TRANSITIONS["T01"], proposal, holder, NOW).outcome == "forbidden"


@pytest.mark.parametrize(
    ("state", "role", "creator", "want"),
    [
        ("idea", "submitter", True, ["T01", "T11"]),
        ("idea", "submitter", False, []),
        ("idea", "organizer", False, ["T01", "T11"]),
        ("planning", "organizer", False, ["T02", "T11"]),
        ("planning", "submitter", True, []),
        ("in_review", "approver", False, ["T03", "T04", "T11"]),
        ("in_review", "organizer", False, ["T11"]),
        ("approved", "editor", False, ["T05", "T06", "T11"]),
        ("live", "editor", False, ["T07"]),
        ("followup", "organizer", False, ["T09"]),
        ("archived", "editor", False, ["T10"]),
        ("withdrawn", "editor", False, ["T12"]),
        ("idea", "viewer", True, []),
    ],
)
def test_allowed_transitions_hint(state: str, role: str, creator: bool, want: list[str]) -> None:
    snapshot = snap(state=state, created_by="me" if creator else "other")
    assert allowed_transitions(snapshot, actor(role, sub="me")) == want


def test_same_input_same_decision() -> None:
    snapshot, who = snap(state="in_review", submitted_by="x"), actor("approver")
    assert decide(TRANSITIONS["T04"], snapshot, who, NOW) == decide(
        TRANSITIONS["T04"], snapshot, who, NOW
    )
    assert replace(snapshot).state == "in_review"


def test_transition_values_follow_the_rules_and_refuse_unknown_ones() -> None:
    from dataclasses import replace

    from app.modules.pipeline.values import transition_values

    values = transition_values(
        TRANSITIONS["T04"],
        actor_sub="me",
        rev=4,
        public_seq=1,
        publish_at=NOW,
        slug="s",
    )
    assert values == {
        "state": "approved",
        "slug": "s",
        "public_seq": 2,
        "approved_by": "me",
        "publish_at": NOW,
    }
    live = transition_values(
        TRANSITIONS["T05"], actor_sub="me", rev=4, public_seq=1, publish_at=None, slug=None
    )
    assert live == {"state": "live", "published_rev": 5}
    offline = transition_values(
        TRANSITIONS["T07"], actor_sub="me", rev=4, public_seq=1, publish_at=None, slug=None
    )
    assert offline["public_status"] == "scheduled" and offline["public_reason_code"] == "none"
    broken = replace(TRANSITIONS["T05"], sets=(("x", "bogus"),))
    with pytest.raises(ValueError, match="bogus"):
        transition_values(broken, actor_sub="me", rev=1, public_seq=0, publish_at=None, slug=None)
