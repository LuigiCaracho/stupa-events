"""U-GUARD-01 to 13: the publish rules (image, exception, date, system, duplicates, race).

The cases that need the database or HTTP (05, 07, 08, 13) live in
`tests/integration/pipeline/test_u_guard_integration.py`; 12 is a property over the three
write paths and lives in `test_publish_property.py`.
"""

from __future__ import annotations

from datetime import timedelta

from app.modules.pipeline.decision import decide
from app.modules.pipeline.snapshot import PosterSnapshot
from app.modules.pipeline.transitions import TRANSITIONS
from tests.unit.pipeline.support import GOOD_POSTER, NOW, actor, snap

REVIEW = {"state": "in_review", "submitted_by": "someone-else"}


def t04(**over: object):  # noqa: ANN201
    return decide(TRANSITIONS["T04"], snap(**{**REVIEW, **over}), actor("editor", "ed"), NOW)


def test_u_guard_01_editor_with_poster_allowed() -> None:
    assert t04().outcome == "ok"


def test_u_guard_02_without_poster_is_image_required() -> None:
    verdict = t04(poster=None)
    assert verdict.outcome == "blocked" and verdict.reasons[0].code == "image_required"


def test_u_guard_03_exception_with_reason_allows() -> None:
    assert t04(poster=None, image_exception_reason="Hochschulveranstaltung").outcome == "ok"


def test_u_guard_04_short_exception_reason_does_not_count() -> None:
    from app.modules.events.access import valid_exception_reason
    from tests.unit.events.test_access_and_revisions import event

    assert valid_exception_reason(event(image_exception={"reason": "kurz"})) is None
    assert t04(poster=None, image_exception_reason=None).outcome == "blocked"


def test_u_guard_06_system_never_publishes_without_a_human() -> None:
    approved = {"state": "approved", "publish_at": NOW - timedelta(minutes=1)}
    system = actor("system")
    for approver in (None, "system:advance_states"):
        verdict = decide(TRANSITIONS["T05"], snap(**approved, approved_by=approver), system, NOW)
        assert verdict.outcome == "blocked"
        assert "not_human_approved" in [r.code for r in verdict.reasons]
    assert decide(TRANSITIONS["T04"], snap(**REVIEW), system, NOW).outcome == "forbidden"
    ok = decide(TRANSITIONS["T05"], snap(**approved, approved_by="person"), system, NOW)
    assert ok.outcome == "ok"


def test_u_guard_07_pending_and_infected_posters_block_t04_and_t05() -> None:
    for status in ("pending", "infected"):
        poster = PosterSnapshot(status, True, "a", "c", "own_work")
        for tid, state in (("T04", "in_review"), ("T05", "approved")):
            snapshot = snap(state=state, poster=poster, submitted_by="x", approved_by="p")
            verdict = decide(TRANSITIONS[tid], snapshot, actor("editor", "ed"), NOW)
            assert verdict.outcome == "blocked"
            assert verdict.reasons[0].code == "image_required"


def test_u_guard_09_a_running_event_is_allowed() -> None:
    running = {"starts_at": NOW - timedelta(hours=1), "ends_at": NOW + timedelta(hours=1)}
    assert t04(**running).outcome == "ok"


def test_u_guard_10_a_past_event_is_start_in_past() -> None:
    verdict = t04(starts_at=NOW - timedelta(days=2), ends_at=NOW - timedelta(days=2, hours=-3))
    assert verdict.outcome == "blocked" and verdict.reasons[0].code == "start_in_past"


def test_u_guard_11_duplicate_is_unresolved() -> None:
    verdict = t04(duplicate_score=0.9)
    assert verdict.outcome == "blocked"
    assert "duplicate_unresolved" in [r.code for r in verdict.reasons]


def test_u_guard_12_same_decision_for_the_same_input() -> None:
    snapshot = snap(**REVIEW)
    first = decide(TRANSITIONS["T04"], snapshot, actor("editor", "ed"), NOW)
    assert all(
        decide(TRANSITIONS["T04"], snapshot, actor("editor", "ed"), NOW) == first for _ in range(3)
    )
    assert snap(poster=GOOD_POSTER).poster is GOOD_POSTER
