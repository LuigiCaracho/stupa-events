"""Wire shapes of the board and list view: the slim `EventCard` and `BoardOut`."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from app.modules.auth.schemas import CamelModel
from app.modules.events.schemas import TransitionName
from app.modules.events.states import PublicStatus
from app.modules.orgs.schemas import OrgRef
from app.modules.pipeline.schemas import ReasonOut
from app.modules.taxonomy.schemas import CategoryRef

ColumnKey = Literal[
    "idea", "planning", "in_review", "published", "followup", "archived", "withdrawn"
]


class PersonRef(CamelModel):
    """A person by `sub` and, when known, display name."""

    sub: str
    display_name: str | None


class EventCard(CamelModel):
    """A dossier as a card: no description, the first blockers of the next move."""

    id: UUID
    title: str
    state: str
    public_status: PublicStatus
    starts_at: datetime
    ends_at: datetime
    tzid: str
    organization: OrgRef | None
    venue_label: str | None
    primary_category: CategoryRef | None
    publish_at: datetime | None
    has_poster: bool
    created_by: PersonRef
    rev: int
    allowed_transitions: list[TransitionName]
    next_transition: TransitionName | None
    blockers: list[ReasonOut]
    blocker_count: int
    moves: dict[str, TransitionName]
    open_questions: int = 0
    all_day: bool = False
    format_slug: str | None = None
    howto_unverified: bool = False


class BoardColumn(CamelModel):
    """One column of the board."""

    key: ColumnKey
    states: list[str]
    total: int
    items: list[EventCard]
    truncated: bool


class BoardOut(CamelModel):
    """The board: its columns and the generation time."""

    columns: list[BoardColumn]
    generated_at: datetime
