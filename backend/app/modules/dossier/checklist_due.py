"""Due dates of checklist items: the rule and the recompute after a change of the start.

`due_at` is 09:00 local time on the local date of `starts_at` plus `due_offset_days`. Only
items that are open, not waived, not set by hand and carry an offset follow the start; a
date set by hand (`due_manual`) or a finished item never moves.
"""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dossier.models_checklist import ChecklistItem
from app.modules.events.models import Event
from app.shared.timeutil import DEFAULT_TZID, utcnow

DUE_HOUR = time(9, 0)


def due_at_for(
    starts_at: datetime | None, tzid: str | None, offset_days: int | None
) -> datetime | None:
    """Return the due moment (UTC) of an item, or `None` without a start or an offset."""
    if starts_at is None or offset_days is None:
        return None
    zone = ZoneInfo(tzid or DEFAULT_TZID)
    day = starts_at.astimezone(zone).date() + timedelta(days=offset_days)
    return datetime.combine(day, DUE_HOUR, tzinfo=zone).astimezone(UTC)


async def recompute_due(session: AsyncSession, event: Event) -> int:
    """Recompute the due dates that follow the start; return how many changed (no commit)."""
    items = await session.scalars(
        select(ChecklistItem).where(
            ChecklistItem.event_id == event.id,
            ChecklistItem.due_manual.is_(False),
            ChecklistItem.done_at.is_(None),
            ChecklistItem.waived_reason.is_(None),
            ChecklistItem.due_offset_days.is_not(None),
        )
    )
    changed = 0
    for item in items:
        due = due_at_for(event.starts_at, event.tzid, item.due_offset_days)
        if due != item.due_at:
            item.due_at = due
            item.updated_at = utcnow()
            changed += 1
    if changed:
        await session.flush()
    return changed
