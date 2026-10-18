"""`due_transition`: the table of contract 6 with its boundaries."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.modules.pipeline.advance import AdvanceRow, due_transition
from tests.unit.pipeline.support import NOW


def row(state: str, **over: object) -> AdvanceRow:
    base = {
        "state": state,
        "publish_at": None,
        "ends_at": NOW - timedelta(days=1),
        "origin_kind": "internal",
        "entered_followup_at": None,
    }
    return AdvanceRow(**{**base, **over})  # type: ignore[arg-type]


def test_approved_waits_for_a_set_and_reached_publish_at() -> None:
    assert due_transition(row("approved"), NOW) is None
    assert due_transition(row("approved", publish_at=NOW + timedelta(seconds=1)), NOW) is None
    assert due_transition(row("approved", publish_at=NOW), NOW) == "T05"
    assert due_transition(row("approved", publish_at=NOW - timedelta(days=1)), NOW) == "T05"


@pytest.mark.parametrize(
    ("ended_ago", "due"),
    [
        (timedelta(hours=11, minutes=59), False),
        (timedelta(hours=12), True),
        (timedelta(hours=12, minutes=1), True),
    ],
)
def test_live_ends_twelve_hours_after_the_end(ended_ago: timedelta, due: bool) -> None:
    got = due_transition(row("live", ends_at=NOW - ended_ago), NOW)
    assert got == ("T08" if due else None)


@pytest.mark.parametrize(
    ("origin", "want"),
    [("internal", "T08"), ("mcp", "T08"), ("imported", "T08b"), ("legacy", "T08b")],
)
def test_live_goes_by_origin(origin: str, want: str) -> None:
    assert due_transition(row("live", origin_kind=origin), NOW) == want


@pytest.mark.parametrize(("days", "want"), [(29, None), (30, "T09b"), (31, "T09b")])
def test_followup_archives_after_thirty_days(days: int, want: str | None) -> None:
    assert (
        due_transition(row("followup", entered_followup_at=NOW - timedelta(days=days)), NOW) == want
    )
    assert due_transition(row("followup"), NOW) is None


@pytest.mark.parametrize("state", ["idea", "planning", "in_review", "archived", "withdrawn"])
def test_other_states_are_never_due(state: str) -> None:
    assert due_transition(row(state, publish_at=NOW), NOW) is None
