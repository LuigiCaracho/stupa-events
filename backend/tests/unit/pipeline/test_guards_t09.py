"""T09 with real guards: the truth table, the order of the reasons and the checklist phase."""

from __future__ import annotations

from itertools import product

import pytest

from app.modules.pipeline.decision import decide
from app.modules.pipeline.guards import (
    checklist_done,
    checklist_done_followup,
    checklist_done_in,
    howto_verified,
    outcome_set_or_waived,
    retrospective_filled,
)
from app.modules.pipeline.reasons import FixAction
from app.modules.pipeline.transitions import TRANSITIONS
from tests.unit.pipeline.support import NOW, actor, snap

CODES = {
    "checklist": "checklist_open",
    "retrospective": "retrospective_missing",
    "outcome": "outcome_missing",
    "howto": "howto_unverified",
}


@pytest.mark.parametrize(
    ("checklist", "retrospective", "outcome", "howto"), list(product((True, False), repeat=4))
)
def test_guards_t09_truth_table(
    checklist: bool, retrospective: bool, outcome: bool, howto: bool
) -> None:
    snapshot = snap(
        state="followup",
        open_required_followup=0 if checklist else 2,
        retrospective_filled=retrospective,
        outcome_set=outcome,
        howto_verified=howto,
    )
    verdict = decide(TRANSITIONS["T09"], snapshot, actor("organizer"), NOW)
    expected = [
        CODES[name]
        for name, ok in zip(CODES, (checklist, retrospective, outcome, howto), strict=True)
        if not ok
    ]
    assert [r.code for r in verdict.reasons] == expected
    assert (verdict.outcome == "ok") is (not expected)


def test_the_fix_actions_and_the_phase_of_the_checklist_reason() -> None:
    snapshot = snap(
        state="followup",
        open_required_followup=1,
        retrospective_filled=False,
        outcome_set=False,
        howto_verified=False,
    )
    reasons = decide(TRANSITIONS["T09"], snapshot, actor("organizer"), NOW).reasons
    assert [r.fix_action for r in reasons] == [
        FixAction.OPEN_CHECKLIST,
        FixAction.FILL_RETROSPECTIVE,
        FixAction.FILL_OUTCOME,
        FixAction.VERIFY_HOWTO,
    ]
    assert reasons[0].field == "followup"
    assert retrospective_filled(snap(), actor("organizer"), NOW) == []
    assert outcome_set_or_waived(snap(), actor("organizer"), NOW) == []
    assert howto_verified(snap(), actor("organizer"), NOW) == []


def test_each_phase_reads_its_own_counter() -> None:
    planning_open = snap(open_required_checklist=2, open_required_followup=0)
    followup_open = snap(open_required_checklist=0, open_required_followup=2)
    assert [r.field for r in checklist_done(planning_open, actor("organizer"), NOW)] == ["planning"]
    assert checklist_done(followup_open, actor("organizer"), NOW) == []
    assert [r.field for r in checklist_done_followup(followup_open, actor("organizer"), NOW)] == [
        "followup"
    ]
    assert checklist_done_followup(planning_open, actor("organizer"), NOW) == []
    assert checklist_done_in("followup")(followup_open, actor("organizer"), NOW)
    with pytest.raises(KeyError):
        checklist_done_in("review")


def test_the_phase_of_each_transition_matches_its_guard() -> None:
    assert TRANSITIONS["T02"].checklist_phase == "planning"
    assert TRANSITIONS["T09"].checklist_phase == "followup"
    assert all(t.checklist_phase == "planning" for k, t in TRANSITIONS.items() if k not in {"T09"})


def test_t09b_and_t08b_ask_for_none_of_it() -> None:
    open_all = snap(
        state="followup",
        retrospective_filled=False,
        outcome_set=False,
        howto_verified=False,
        open_required_followup=3,
        entered_followup_at=NOW.replace(year=2026, month=9, day=1),
    )
    verdict = decide(TRANSITIONS["T09b"], open_all, actor("system"), NOW)
    assert verdict.outcome == "ok"
