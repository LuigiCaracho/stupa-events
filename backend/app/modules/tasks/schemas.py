"""Wire shapes of `GET /tasks` (camelCase)."""

from __future__ import annotations

from datetime import datetime

from app.modules.auth.schemas import CamelModel
from app.modules.events.card_schemas import EventCard, PersonRef
from app.modules.events.revision_views import RevisionOut


class AwaitingCard(EventCard):
    """A dossier waiting for the caller's approval."""

    four_eyes_blocked: bool


class ReturnedCard(EventCard):
    """A dossier sent back to planning, with the note of the reviewer."""

    note: str | None
    returned_at: datetime
    returned_by: PersonRef


class ChangedCard(EventCard):
    """A live dossier whose text changed since publication or since the last review."""

    baseline_rev: int
    changes: list[RevisionOut]


class TaskCounts(CamelModel):
    """The full number behind each list (the lists hold at most 50)."""

    awaiting_review: int
    returned: int
    due: int
    mine: int
    followup_open: int
    changed_after_publish: int


class TasksOut(CamelModel):
    """What the caller can do now."""

    awaiting_review: list[AwaitingCard]
    returned: list[ReturnedCard]
    due: list[EventCard]
    mine: list[EventCard]
    followup_open: list[EventCard]
    changed_after_publish: list[ChangedCard]
    counts: TaskCounts
