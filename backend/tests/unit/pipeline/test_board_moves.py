"""`BOARD_MOVES` agrees with `TRANSITIONS`; the permission catalogue holds `event.restore`."""

from __future__ import annotations

from app.modules.events.board import (
    BOARD_MOVES,
    COLUMN_OF_STATE,
    COLUMNS,
    PRIMARY_TRANSITION,
    moves_for,
)
from app.modules.events.states import EventState
from app.modules.pipeline.transitions import TRANSITIONS
from app.shared.permissions import PERMISSION_CATALOGUE, ROLE_PERMISSIONS


def test_every_board_move_is_a_transition_between_the_two_columns() -> None:
    for (source, column), tid in BOARD_MOVES.items():
        transition = TRANSITIONS[tid]
        assert EventState(source) in transition.source
        assert COLUMN_OF_STATE[transition.target.value] == column


def test_columns_cover_every_state_once() -> None:
    states = [s for column in COLUMNS.values() for s in column]
    assert sorted(states) == sorted(s.value for s in EventState)


def test_primary_transitions_start_in_their_state() -> None:
    for state, tid in PRIMARY_TRANSITION.items():
        assert EventState(state) in TRANSITIONS[tid].source


def test_moves_for_keeps_only_allowed_transitions() -> None:
    assert moves_for("in_review", ["T03", "T04"]) == {"planning": "T03", "published": "T04"}
    assert moves_for("in_review", ["T04"]) == {"published": "T04"}
    assert moves_for("live", ["T07"]) == {}


def test_event_restore_belongs_to_the_editor_only() -> None:
    assert "event.restore" in PERMISSION_CATALOGUE
    holders = {role for role, perms in ROLE_PERMISSIONS.items() if "event.restore" in perms}
    assert holders == {"editor"}
