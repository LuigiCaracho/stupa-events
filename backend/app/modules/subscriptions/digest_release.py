"""Release of a digest draft: the one step that lets Listmonk send.

The release is refused while the circuit breaker is open or while the Listmonk subscriber count
of the list differs from the number of our confirmed subscribers who want mail on that list
(PLAN 8.7.7): a mismatch means an unreconciled opt-out or a stranger on the list. A dead erasure job blocks
it too.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.subscriptions.listmonk_port import ListmonkPort
from app.modules.subscriptions.listmonk_sync import ALL_KEY
from app.modules.subscriptions.models import (
    DigestRun,
    ListmonkList,
    Outbox,
    Subscriber,
    SubscriptionProfile,
)
from app.modules.subscriptions.outbox import BREAKER_KEY, Breaker
from app.shared.timeutil import utcnow

Maker = async_sessionmaker[AsyncSession]


class ReleaseBlockedError(Exception):
    """The release is refused; `code` names the reason for the admin UI."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


async def own_count(maker: Maker, key: str) -> int:
    """Count confirmed subscribers who want mail and belong on the list `key`."""
    stmt = (
        select(func.count())
        .select_from(Subscriber)
        .join(SubscriptionProfile, SubscriptionProfile.subscriber_id == Subscriber.id)
        .where(Subscriber.status == "confirmed", SubscriptionProfile.mail_enabled.is_(True))
    )
    if key != ALL_KEY:
        stmt = stmt.where(SubscriptionProfile.categories.contains([key]))
    async with maker() as session:
        return int(await session.scalar(stmt) or 0)


async def dead_erasures(maker: Maker) -> int:
    """Count `delete` and `unsubscribe` jobs that gave up: an erased person may still be listed."""
    stmt = (
        select(func.count())
        .select_from(Outbox)
        .where(Outbox.state == "dead", Outbox.op.in_(("delete", "unsubscribe")))
    )
    async with maker() as session:
        return int(await session.scalar(stmt) or 0)


async def release_digest(
    maker: Maker,
    port: ListmonkPort,
    run_id: uuid.UUID,
    *,
    by_sub: str,
    breaker: Breaker | None = None,
    now: datetime | None = None,
) -> None:
    """Start the campaign of a draft digest and mark the run released.

    Raises:
        ReleaseBlockedError: Unknown or not a draft (`not_draft`), Listmonk down
            (`listmonk_unavailable`), an erasure job is dead (`erasure_pending`) or the counts differ
            (`count_mismatch`).
    """
    async with maker() as session:
        run = await session.get(DigestRun, run_id)
        listed = (
            await session.scalar(select(ListmonkList).where(ListmonkList.key == run.list_key))
            if run
            else None
        )
    if run is None or run.status != "draft" or run.campaign_id is None or listed is None:
        raise ReleaseBlockedError("not_draft")
    if breaker is not None and await breaker.exists(BREAKER_KEY):
        raise ReleaseBlockedError("listmonk_unavailable")
    if await dead_erasures(maker):
        raise ReleaseBlockedError("erasure_pending")
    if await port.subscriber_count(listed.listmonk_id) != await own_count(maker, run.list_key):
        raise ReleaseBlockedError("count_mismatch")
    await port.start_campaign(run.campaign_id)
    async with maker.begin() as session:
        await session.execute(
            update(DigestRun)
            .where(DigestRun.id == run_id)
            .values(status="released", released_by_sub=by_sub, released_at=now or utcnow())
        )


async def mark_released_in_listmonk(maker: Maker, port: ListmonkPort) -> int:
    """Mark drafts whose campaign someone started in Listmonk; return how many."""
    async with maker() as session:
        drafts = (
            await session.execute(
                select(DigestRun.id, DigestRun.campaign_id).where(DigestRun.status == "draft")
            )
        ).all()
    changed = 0
    for run_id, campaign_id in drafts:
        if campaign_id is None or await port.campaign_status(campaign_id) == "draft":
            continue
        async with maker.begin() as session:
            await session.execute(
                update(DigestRun)
                .where(DigestRun.id == run_id, DigestRun.status == "draft")
                .values(status="released", released_at=utcnow())
            )
        changed += 1
    return changed
