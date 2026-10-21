"""Wire shape of the list view: the slim `EventCard`."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.modules.auth.schemas import CamelModel
from app.modules.events.states import PublicStatus
from app.modules.orgs.schemas import OrgRef
from app.modules.taxonomy.schemas import CategoryRef


class PersonRef(CamelModel):
    """A person by `sub` and, when known, display name."""

    sub: str
    display_name: str | None


class EventCard(CamelModel):
    """A dossier as a card: the base data, the poster mark and the number of warnings."""

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
    has_poster: bool
    created_by: PersonRef
    rev: int
    open_questions: int = 0
    hint_count: int = 0
    all_day: bool = False
    format_slug: str | None = None
    howto_unverified: bool = False
