"""Board vocabulary: columns, the drag moves of the board and the primary move per state."""

from __future__ import annotations

from collections.abc import Mapping

from app.modules.events.card_schemas import ColumnKey
from app.modules.events.states import EventState as S

COLUMNS: Mapping[str, tuple[str, ...]] = {
    "idea": (S.IDEA.value,),
    "planning": (S.PLANNING.value,),
    "in_review": (S.IN_REVIEW.value,),
    "published": (S.APPROVED.value, S.LIVE.value),
    "followup": (S.FOLLOWUP.value,),
    "archived": (S.ARCHIVED.value,),
    "withdrawn": (S.WITHDRAWN.value,),
}
ACTIVE_COLUMNS: tuple[ColumnKey, ...] = ("idea", "planning", "in_review", "published", "followup")
DESCENDING_COLUMNS = frozenset({"followup", "archived", "withdrawn"})
COLUMN_OF_STATE: Mapping[str, str] = {s: key for key, states in COLUMNS.items() for s in states}

BOARD_MOVES: Mapping[tuple[str, str], str] = {
    ("idea", "planning"): "T01",
    ("planning", "in_review"): "T02",
    ("in_review", "planning"): "T03",
    ("in_review", "published"): "T04",
    ("approved", "in_review"): "T06",
}
PRIMARY_TRANSITION: Mapping[str, str] = {
    "idea": "T01",
    "planning": "T02",
    "in_review": "T04",
    "approved": "T05",
    "followup": "T09",
}


def moves_for(state: str, allowed: list[str]) -> dict[str, str]:
    """Return `{column: transition}` for the columns a card in `state` may be dragged to."""
    return {
        column: tid
        for (source, column), tid in BOARD_MOVES.items()
        if source == state and tid in allowed
    }
