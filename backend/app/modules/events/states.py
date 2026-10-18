"""Vocabulary of the event pipeline: states, public status and transition ids (PLAN 4.1).

Only T01, T02, T04 and T05 are reachable in M1. The remaining states exist in the database
so that M3 needs no migration of the CHECK constraints.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal


class EventState(StrEnum):
    """Pipeline state of a dossier."""

    IDEA = "idea"
    PLANNING = "planning"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    LIVE = "live"
    FOLLOWUP = "followup"
    ARCHIVED = "archived"
    WITHDRAWN = "withdrawn"


class PublicStatus(StrEnum):
    """Orthogonal public status, visible from `live` on."""

    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


type TransitionId = Literal["T01", "T02", "T04", "T05"]

EDITABLE_STATES: frozenset[EventState] = frozenset({EventState.IDEA, EventState.PLANNING})
PUBLIC_STATES: tuple[EventState, ...] = (
    EventState.LIVE,
    EventState.FOLLOWUP,
    EventState.ARCHIVED,
)
