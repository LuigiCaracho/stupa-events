"""arq cron job `send_followup_reminders`: one reminder a week after a dossier entered `followup`.

The entry is the latest `event_status_event` with `to_state = 'followup'`, so a dossier that
leaves the archive through T10 starts a new week and gets a new reminder. The dedupe key
carries the day of the entry. A Redis claim with the same key, set only after the commit,
stops a second run from sending the mails again (a person with the inbox switched off has no
row to dedupe on); a failed commit leaves no claim, so the next run retries. Like
`send_due_reminders` it needs the queue: without Redis it skips.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_sessionmaker
from app.modules.events.access import guard_snapshot, poster_of
from app.modules.events.models import Event, EventStatusEvent
from app.modules.followup.missing import days_open, missing_of
from app.modules.notifications.service import PendingMail, dispatch_mails, notify_event
from app.shared.timeutil import utcnow

logger = logging.getLogger("worker.followup")

REMINDER_AFTER = timedelta(days=7)
CLAIM_TTL_SECONDS = 40 * 24 * 3600
BATCH = 500


def _sessionmaker(ctx: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    maker = ctx.get("followup_sessionmaker")
    return maker if maker is not None else get_sessionmaker()


async def _due(session: AsyncSession, now: datetime) -> list[tuple[Event, datetime]]:
    entered = (
        select(EventStatusEvent.event_id, func.max(EventStatusEvent.at).label("at"))
        .where(EventStatusEvent.to_state == "followup")
        .group_by(EventStatusEvent.event_id)
        .subquery()
    )
    rows = await session.execute(
        select(Event, entered.c.at)
        .join(entered, entered.c.event_id == Event.id)
        .where(Event.state == "followup", entered.c.at + REMINDER_AFTER <= now)
        .order_by(entered.c.at)
        .limit(BATCH)
    )
    return [(event, at) for event, at in rows.all()]


async def send_followup_reminders(ctx: dict[str, Any], now: datetime | None = None) -> str:
    """Remind the owners of every dossier that waited seven days in `followup`.

    Returns:
        The log line `send_followup_reminders: events=<n> mails=<m>`.
    """
    if ctx.get("redis") is None:
        return "send_followup_reminders: skipped (no queue)"
    moment = now or utcnow()
    pending: list[PendingMail] = []
    claims: list[str] = []
    async with _sessionmaker(ctx)() as session:
        due = await _due(session, moment)
        for event, entered in due:
            key = f"followup_reminder:{event.id}:{entered:%Y%m%dT%H%M%S%f}"
            if await ctx["redis"].exists(key):
                continue
            claims.append(key)
            snapshot = await guard_snapshot(session, event, await poster_of(session, event))
            pending += await notify_event(
                session,
                "followup_reminder",
                event,
                {"daysOpen": days_open(entered, moment), "missing": missing_of(snapshot)},
                key,
            )
        await session.commit()
    for key in claims:
        await ctx["redis"].set(key, "1", ex=CLAIM_TTL_SECONDS)
    await dispatch_mails(ctx.get("redis"), pending)
    return f"send_followup_reminders: events={len(due)} mails={len(pending)}"
