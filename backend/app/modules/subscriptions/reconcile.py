"""Daily reconcile of our subscribers with the Listmonk lists.

Our record wins everywhere except at an opt-out, which is monotonic. The run reads every
non-archived list page by page and then: (a) takes over a blocklisted subscriber, or one who left
every wanted list, as `unsubscribed`, (b) drops a category from the profile when the person left
just that list, (c) removes a stranger on an `events-*` list from the lists (the Listmonk instance
is shared, so nothing is deleted) and counts it, (d) queues an `upsert` for a confirmed subscriber
who is missing from Listmonk or from a wanted list, and (e) marks digest drafts that were released
inside Listmonk. Only counters leave this module, never addresses. Bounces are not read: the
subscriber API cannot tell a bounce from a manual block.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.subscriptions.digest_release import mark_released_in_listmonk
from app.modules.subscriptions.listmonk_port import ListmonkPort, ListmonkSubscriber
from app.modules.subscriptions.listmonk_sync import (
    ALL_KEY,
    Target,
    desired_keys,
    mark_unsubscribed,
    plan,
    sync_category_lists,
)
from app.modules.subscriptions.models import ListmonkList, Subscriber, SubscriptionProfile
from app.modules.subscriptions.outbox import requeue_upsert
from app.shared.timeutil import utcnow

logger = logging.getLogger("app.subscriptions.reconcile")

Maker = async_sessionmaker[AsyncSession]


@dataclass(slots=True)
class Report:
    """Counters of one reconcile run."""

    seen: int = 0
    unsubscribed: int = 0
    categories_dropped: int = 0
    foreign_on_lists: int = 0
    requeued: int = 0
    released_digests: int = 0


async def _by_email(maker: Maker, email_key: str) -> dict[str, Target]:
    stmt = (
        select(
            func.pgp_sym_decrypt(Subscriber.email_enc, email_key),
            Subscriber.id,
            Subscriber.status,
            Subscriber.listmonk_subscriber_id,
            SubscriptionProfile.id,
            SubscriptionProfile.categories,
            SubscriptionProfile.mail_enabled,
        )
        .select_from(Subscriber)
        .outerjoin(SubscriptionProfile, SubscriptionProfile.subscriber_id == Subscriber.id)
        .where(Subscriber.email_enc.is_not(None), Subscriber.status != "pending")
    )
    async with maker() as session:
        rows = (await session.execute(stmt)).all()
    return {
        email.lower(): Target(sid, email, status, lid, pid, list(cats or []), bool(mail), 0)
        for email, sid, status, lid, pid, cats, mail in rows
    }


async def _drop_categories(maker: Maker, target: Target, left: set[str]) -> None:
    kept = [c for c in target.categories if c not in left]
    async with maker.begin() as session:
        await session.execute(
            update(SubscriptionProfile)
            .where(SubscriptionProfile.subscriber_id == target.subscriber_id)
            .values(categories=kept, updated_at=utcnow())
        )


async def reconcile(
    maker: Maker, port: ListmonkPort, email_key: str, *, now: datetime | None = None
) -> Report:
    """Run the reconcile once and return the counters."""
    moment = now or utcnow()
    report = Report()
    await sync_category_lists(maker, port)
    async with maker() as session:
        lists = [r[0] for r in (await session.execute(select(ListmonkList))).all()]
    key_of = {row.listmonk_id: row.key for row in lists if row.archived_at is None}
    ours = await _by_email(maker, email_key)
    seen: set[str] = set()
    async for remote in port.list_states(set(key_of)):
        report.seen += 1
        target = ours.get(remote.email.lower())
        if target is None or target.status == "erased":
            await _remove_foreign(port, remote, key_of, report)
        elif target.status == "confirmed":
            seen.add(remote.email.lower())
            await _reconcile_one(maker, remote, target, key_of, report, moment)
    for email, target in ours.items():
        if target.status == "confirmed" and target.mail_enabled and email not in seen:
            await requeue_upsert(maker, target.subscriber_id, moment)
            report.requeued += 1
    report.released_digests = await mark_released_in_listmonk(maker, port)
    logger.info(
        "reconcile seen=%s unsubscribed=%s dropped=%s foreign=%s requeued=%s released=%s",
        report.seen,
        report.unsubscribed,
        report.categories_dropped,
        report.foreign_on_lists,
        report.requeued,
        report.released_digests,
    )
    return report


async def _reconcile_one(
    maker: Maker,
    remote: ListmonkSubscriber,
    target: Target,
    key_of: dict[int, str],
    report: Report,
    now: datetime,
) -> None:
    wanted_keys = desired_keys(target.mail_enabled, target.categories)
    wanted_ids = {i for i, k in key_of.items() if k in wanted_keys}
    if plan(remote, wanted_ids).action == "opted_out":
        await mark_unsubscribed(maker, target.subscriber_id, now)
        report.unsubscribed += 1
        return
    left = {key_of[i] for i, s in remote.lists.items() if s == "unsubscribed" and i in key_of}
    dropped = (left - {ALL_KEY}) & set(target.categories)
    if dropped:
        await _drop_categories(maker, target, dropped)
        report.categories_dropped += 1
    elif wanted_keys and (wanted_ids - remote.lists.keys() or wanted_keys - set(key_of.values())):
        await requeue_upsert(maker, target.subscriber_id, now)
        report.requeued += 1


async def _remove_foreign(
    port: ListmonkPort, remote: ListmonkSubscriber, key_of: dict[int, str], report: Report
) -> None:
    if not any(s != "unsubscribed" for i, s in remote.lists.items() if i in key_of):
        return
    await port.upsert_subscriber(remote.email, set(remote.lists) - set(key_of), {})
    report.foreign_on_lists += 1
