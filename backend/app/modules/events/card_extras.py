"""Guard inputs of many cards at once, so a card shows the same blockers as `GET /guards`.

`guard_snapshot` reads three values per dossier with its own queries (quarantined
attachments, the last entry into `followup`, a poster reused in another year). A board
of 50 cards reads them here with one grouped query each instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.modules.events.access import snapshot_of
from app.modules.events.models import Event, EventStatusEvent
from app.modules.files.models import Attachment
from app.modules.pipeline.snapshot import Snapshot
from app.shared.timeutil import DEFAULT_TZID


@dataclass(frozen=True, slots=True)
class CardExtras:
    """The per-dossier values that `snapshot_of` cannot read from the row."""

    quarantined: dict[UUID, int]
    entered_followup: dict[UUID, datetime]
    reused_posters: set[UUID]

    def snapshot(self, event: Event, poster: Attachment | None) -> Snapshot:
        """Build the full guard snapshot of one card."""
        snapshot = snapshot_of(
            event,
            poster,
            quarantined_attachments=self.quarantined.get(event.id, 0),
            entered_followup_at=self.entered_followup.get(event.id),
        )
        if snapshot.poster is None or event.id not in self.reused_posters:
            return snapshot
        return replace(snapshot, poster=replace(snapshot.poster, reused_in_other_year=True))


async def load_card_extras(session: AsyncSession, events: Sequence[Event]) -> CardExtras:
    """Read the extras of all `events` with three grouped queries."""
    ids = [e.id for e in events]
    if not ids:
        return CardExtras({}, {}, set())
    return CardExtras(
        await _quarantined(session, ids),
        await _entered_followup(session, ids),
        await _reused_posters(session, ids),
    )


async def _quarantined(session: AsyncSession, ids: list[UUID]) -> dict[UUID, int]:
    rows = await session.execute(
        select(Attachment.event_id, func.count())
        .join(Event, Event.id == Attachment.event_id)
        .where(
            Attachment.event_id.in_(ids),
            Attachment.retired_at.is_(None),
            Attachment.scan_status != "clean",
            Attachment.id.is_distinct_from(Event.hero_attachment_id),
        )
        .group_by(Attachment.event_id)
    )
    return {event_id: count for event_id, count in rows.all()}


async def _entered_followup(session: AsyncSession, ids: list[UUID]) -> dict[UUID, datetime]:
    rows = await session.execute(
        select(EventStatusEvent.event_id, func.max(EventStatusEvent.at))
        .where(EventStatusEvent.event_id.in_(ids), EventStatusEvent.to_state == "followup")
        .group_by(EventStatusEvent.event_id)
    )
    return {event_id: at for event_id, at in rows.all()}


async def _reused_posters(session: AsyncSession, ids: list[UUID]) -> set[UUID]:
    hero, other = aliased(Attachment), aliased(Attachment)
    other_event = aliased(Event)
    own_year = func.extract(
        "year", func.timezone(func.coalesce(Event.tzid, DEFAULT_TZID), Event.starts_at)
    )
    other_year = func.extract("year", func.timezone(DEFAULT_TZID, other_event.starts_at))
    rows = await session.scalars(
        select(Event.id)
        .distinct()
        .join(hero, hero.id == Event.hero_attachment_id)
        .join(other, (other.sha256 == hero.sha256) & (other.event_id != Event.id))
        .join(other_event, other_event.id == other.event_id)
        .where(Event.id.in_(ids), other.retired_at.is_(None), other_year != own_year)
    )
    return set(rows)
