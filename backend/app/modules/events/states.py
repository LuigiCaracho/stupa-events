"""Vocabulary of the event dossier: the three states, the public status and the lifecycle actions.

A dossier is a `draft`, `published` or `archived`. The public status (`scheduled`,
`cancelled`, `postponed`) is orthogonal and changes only while the dossier is published.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal


class EventState(StrEnum):
    """Lifecycle state of a dossier."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class PublicStatus(StrEnum):
    """Orthogonal public status, changeable while the dossier is published."""

    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"
    POSTPONED = "postponed"


type LifecycleAction = Literal[
    "publish", "unpublish", "archive", "restore", "cancel", "postpone", "reinstate"
]

PUBLIC_STATES: tuple[EventState, ...] = (EventState.PUBLISHED, EventState.ARCHIVED)
