"""Worker jobs of the lifecycle: `archive_ended` every quarter hour and `purge_drafts` daily.

`archive_ended` archives every published dossier twelve hours after its end (a cancelled
one too), each in its own session and transaction through `lifecycle.archive_as_system`.
One failing dossier never stops the run. The return value is the line for the arq log.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_sessionmaker
from app.modules.events import drafts, lifecycle
from app.modules.events.models import Event
from app.modules.events.postcommit import run_actions
from app.modules.events.states import EventState
from app.modules.notifications.service import dispatch_mails
from app.shared.errors import ConflictError
from app.shared.timeutil import utcnow

logger = logging.getLogger("worker.advance")

BATCH = 200
ARCHIVE_AFTER = timedelta(hours=12)


def _sessionmaker(ctx: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    maker = ctx.get("advance_sessionmaker")
    return maker if maker is not None else get_sessionmaker()


async def ended_ids(
    session: AsyncSession, now: datetime, exclude: frozenset[UUID] = frozenset()
) -> list[UUID]:
    """Select the published dossiers that ended twelve hours ago, oldest first, at most `BATCH`.

    `exclude` holds the ids already tried in this run, so a page of dossiers that stay
    published never hides the due ones behind it.
    """
    rows = await session.scalars(
        select(Event.id)
        .where(
            Event.state == EventState.PUBLISHED.value,
            Event.ends_at <= now - ARCHIVE_AFTER,
            Event.id.not_in(exclude),
        )
        .order_by(Event.ends_at)
        .limit(BATCH)
    )
    return list(rows)


async def archive_one(maker: async_sessionmaker[AsyncSession], pool: Any, event_id: UUID) -> str:
    """Archive one dossier in its own transaction; return the outcome word."""
    async with maker() as session:
        event = await session.get(Event, event_id)
        if event is None:
            return "skipped"
        try:
            fired = await lifecycle.archive_as_system(session, event)
        except ConflictError:
            await session.rollback()
            return "skipped"
        await session.commit()
    await run_actions(pool, fired.actions, fired.committed)
    await dispatch_mails(pool, fired.mails)
    return "archived"


async def archive_ended(ctx: dict[str, Any], now: datetime | None = None) -> str:
    """Cron entry point: archive every published dossier that ended twelve hours ago.

    Returns:
        The log line `archived=<n> failed=<n>`.
    """
    moment = now or utcnow()
    maker = _sessionmaker(ctx)
    counts: Counter[str] = Counter()
    seen: frozenset[UUID] = frozenset()
    while True:
        async with maker() as session:
            page = await ended_ids(session, moment, seen)
        if not page:
            break
        seen |= set(page)
        for event_id in page:
            try:
                counts[await archive_one(maker, ctx.get("redis"), event_id)] += 1
            except Exception:  # noqa: BLE001 - one dossier never stops the run
                logger.exception("archive failed event=%s", event_id)
                counts["failed"] += 1
    return f"archived={counts['archived']} failed={counts['failed']}"


async def purge_drafts(ctx: dict[str, Any], now: datetime | None = None) -> str:
    """Daily cron: delete drafts idle for more than 14 days."""
    async with _sessionmaker(ctx)() as session:
        removed = await drafts.purge_older_than(session, now or utcnow())
        await session.commit()
    return f"purged={removed}"
