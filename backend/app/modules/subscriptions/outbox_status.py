"""Counters for the status page (I25): outbox backlog and the last reconcile.

`outbox_lag_seconds` is the age of the oldest job that still waits; the alarm criterion is a
backlog older than one hour. A `dead` `delete` job is a legal alarm (the erased person is still in
Listmonk) with a 24 hour deadline. The reconcile job leaves its counters in Redis for three days.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.subscriptions.models import Outbox
from app.modules.subscriptions.reconcile import Report
from app.shared.timeutil import utcnow

RECONCILE_KEY = "listmonk:reconcile"
RECONCILE_TTL_SECONDS = 3 * 24 * 3600

Maker = async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class OutboxStatus:
    """The numbers of the status page."""

    outbox_pending: int
    outbox_dead: int
    outbox_dead_deletes: int
    outbox_lag_seconds: int


async def outbox_status(maker: Maker, now: datetime | None = None) -> OutboxStatus:
    """Read the backlog counters."""
    moment = now or utcnow()
    stmt = select(
        func.count().filter(Outbox.state.in_(("pending", "running"))),
        func.count().filter(Outbox.state == "dead"),
        func.count().filter(Outbox.state == "dead", Outbox.op == "delete"),
        func.min(Outbox.created_at).filter(Outbox.state.in_(("pending", "running"))),
    )
    async with maker() as session:
        pending, dead, dead_deletes, oldest = (await session.execute(stmt)).one()
    lag = int((moment - oldest).total_seconds()) if oldest else 0
    return OutboxStatus(pending, dead, dead_deletes, max(lag, 0))


async def store_reconcile(redis: Any, report: Report, now: datetime | None = None) -> None:
    """Keep the counters of the last reconcile for the status page."""
    payload = {**asdict(report), "at": (now or utcnow()).isoformat()}
    await redis.set(RECONCILE_KEY, json.dumps(payload), ex=RECONCILE_TTL_SECONDS)


async def last_reconcile(redis: Any) -> dict[str, object] | None:
    """Return the stored counters of the last reconcile or None."""
    raw = await redis.get(RECONCILE_KEY)
    return json.loads(raw) if raw else None
