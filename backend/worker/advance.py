"""Worker jobs of the pipeline: `advance_states` every quarter hour and `purge_drafts` daily.

`advance_states` picks the dossiers for which `due_transition` names a transition and
fires each one in its own session and transaction through
`PipelineService.stage_system_fire`, the same `decide` as the REST route. A guard that
blocks (a poster that turned invalid) leaves the dossier where it is. One failing dossier
never stops the run. The return value is the line for the arq log.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_sessionmaker
from app.modules.events import drafts
from app.modules.events.models import Event, EventStatusEvent
from app.modules.pipeline.actions import run_actions
from app.modules.pipeline.advance import ENDED_GRACE, FOLLOWUP_GRACE, AdvanceRow, due_transition
from app.modules.pipeline.service import PipelineService
from app.shared.errors import ConflictError, ValidationProblem
from app.shared.timeutil import utcnow

logger = logging.getLogger("worker.advance")

BATCH = 200
_SYSTEM_TRANSITIONS = {
    "T05": "published",
    "T08": "followup",
    "T08b": "archived",
    "T09b": "archived",
}


def _sessionmaker(ctx: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    maker = ctx.get("advance_sessionmaker")
    return maker if maker is not None else get_sessionmaker()


async def candidates(
    session: AsyncSession, now: datetime, exclude: frozenset[Any] = frozenset()
) -> list[tuple[Event, AdvanceRow]]:
    """Select the dossiers that may be due, at most `BATCH` per class, most overdue first.

    `exclude` holds the ids already tried in this run, so a page of dossiers that stay
    blocked never hides the due ones behind it.
    """
    entered = (
        select(EventStatusEvent.event_id, func.max(EventStatusEvent.at).label("at"))
        .where(EventStatusEvent.to_state == "followup")
        .group_by(EventStatusEvent.event_id)
        .subquery()
    )
    approved = (
        select(Event, entered.c.at)
        .outerjoin(entered, entered.c.event_id == Event.id)
        .where(
            Event.state == "approved",
            Event.publish_at.is_not(None),
            Event.publish_at <= now,
            Event.id.not_in(exclude),
        )
        .order_by(Event.publish_at)
        .limit(BATCH)
    )
    live = (
        select(Event, entered.c.at)
        .outerjoin(entered, entered.c.event_id == Event.id)
        .where(Event.state == "live", Event.ends_at <= now - ENDED_GRACE, Event.id.not_in(exclude))
        .order_by(Event.ends_at)
        .limit(BATCH)
    )
    followup = (
        select(Event, entered.c.at)
        .join(entered, entered.c.event_id == Event.id)
        .where(
            Event.state == "followup",
            entered.c.at <= now - FOLLOWUP_GRACE,
            Event.id.not_in(exclude),
        )
        .order_by(entered.c.at)
        .limit(BATCH)
    )
    found: list[tuple[Event, AdvanceRow]] = []
    for query in (approved, live, followup):
        for event, at in (await session.execute(query)).all():
            found.append(
                (
                    event,
                    AdvanceRow(event.state, event.publish_at, event.ends_at, event.origin_kind, at),
                )
            )
    return found


async def advance_one(
    maker: async_sessionmaker[AsyncSession],
    pool: Any,
    event_id: Any,
    transition: str,
    now: datetime,
) -> str:
    """Fire one system transition in its own transaction; return the outcome word."""
    async with maker() as session:
        try:
            fired = await PipelineService(session).stage_system_fire(event_id, transition, now)
        except ConflictError:
            await session.rollback()
            return "skipped"
        except ValidationProblem as exc:
            await session.rollback()
            logger.warning("advance_blocked event=%s code=%s", event_id, exc.code)
            return "blocked"
        await session.commit()
    await run_actions(pool, fired.actions, fired.committed)
    return _SYSTEM_TRANSITIONS[transition]


async def advance_states(ctx: dict[str, Any], now: datetime | None = None) -> str:
    """Cron entry point: move every due dossier one step.

    Returns:
        A summary such as `published=1 followup=0 archived=0 blocked=0 skipped=0 failed=0`.
    """
    moment = now or utcnow()
    maker = _sessionmaker(ctx)
    counts: Counter[str] = Counter()
    seen: frozenset[Any] = frozenset()
    while True:
        async with maker() as session:
            page = await candidates(session, moment, seen)
        if not page:
            break
        seen |= {event.id for event, _ in page}
        due = [
            (event.id, transition)
            for event, row in page
            if (transition := due_transition(row, moment)) is not None
        ]
        for event_id, transition in due:
            try:
                counts[
                    await advance_one(maker, ctx.get("redis"), event_id, transition, moment)
                ] += 1
            except Exception:  # noqa: BLE001 - one dossier never stops the run
                logger.exception("advance failed event=%s transition=%s", event_id, transition)
                counts["failed"] += 1
    return " ".join(
        f"{key}={counts[key]}"
        for key in ("published", "followup", "archived", "blocked", "skipped", "failed")
    )


async def purge_drafts(ctx: dict[str, Any], now: datetime | None = None) -> str:
    """Daily cron: delete drafts idle for more than 14 days."""
    async with _sessionmaker(ctx)() as session:
        removed = await drafts.purge_older_than(session, now or utcnow())
        await session.commit()
    return f"purged={removed}"
