"""Guard inputs of many cards at once, so a card shows the same blockers as `GET /guards`.

`guard_snapshot` reads the guard inputs of one dossier (`dossier.guard_data`: comments,
checklist, quarantine, reused poster, plus the last entry into `followup`). A board of 50
cards reads them here with one grouped query each instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dossier.guard_data import GuardData, load_guard_data
from app.modules.events.access import snapshot_with
from app.modules.events.models import Event, EventStatusEvent
from app.modules.files.models import Attachment
from app.modules.pipeline.snapshot import Snapshot


@dataclass(frozen=True, slots=True)
class CardExtras:
    """The per-dossier values that `snapshot_of` cannot read from the row."""

    guard_data: dict[UUID, GuardData]
    entered_followup: dict[UUID, datetime]

    def has_howto(self, event_id: UUID) -> bool:
        """Tell if the dossier has a howto of its own or the master howto of its format."""
        return self.guard_data.get(event_id, GuardData()).howto_present

    def snapshot(self, event: Event, poster: Attachment | None) -> Snapshot:
        """Build the full guard snapshot of one card."""
        return snapshot_with(
            event,
            poster,
            self.guard_data.get(event.id, GuardData()),
            self.entered_followup.get(event.id),
        )


async def load_card_extras(session: AsyncSession, events: Sequence[Event]) -> CardExtras:
    """Read the extras of all `events` with a few grouped queries."""
    ids = [e.id for e in events]
    if not ids:
        return CardExtras({}, {})
    return CardExtras(await load_guard_data(session, events), await _entered_followup(session, ids))


async def _entered_followup(session: AsyncSession, ids: list[UUID]) -> dict[UUID, datetime]:
    rows = await session.execute(
        select(EventStatusEvent.event_id, func.max(EventStatusEvent.at))
        .where(EventStatusEvent.event_id.in_(ids), EventStatusEvent.to_state == "followup")
        .group_by(EventStatusEvent.event_id)
    )
    return {event_id: at for event_id, at in rows.all()}
