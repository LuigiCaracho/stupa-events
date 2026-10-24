"""Outbox runner: brings Listmonk to the wanted state, with retry, backoff and a circuit breaker.

A run claims due jobs with `FOR UPDATE SKIP LOCKED` and handles them one after the other. A
handler never replays a delta: `upsert` reads the subscriber and the profile as they are now
and aligns Listmonk with that, so a late job cannot do harm. `confirm` and `delete` never wait
for Listmonk; a down Listmonk only makes the outbox grow. A failed job is retried with
`min(30 s * 2^attempts, 1 h)`; after ten tries (three for an error that retrying cannot fix) it
is `dead`. Five failures in a row end the run and open the breaker in Redis for five minutes.
Errors keep only the class and the status, never an address.
"""

from __future__ import annotations

import base64
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.subscriptions import listmonk_sync as sync
from app.modules.subscriptions.listmonk_port import ListmonkError, ListmonkPort
from app.modules.subscriptions.models import Outbox
from app.shared.timeutil import utcnow

logger = logging.getLogger("app.subscriptions.outbox")

BREAKER_KEY = "listmonk:open"
BREAKER_SECONDS = 300
BATCH = 50
MAX_ATTEMPTS = 10
MAX_ATTEMPTS_PERMANENT = 3
BREAKER_FAILURES = 5
ORPHAN_AFTER = timedelta(minutes=5)
CIPHERTEXT_OPS = ("delete", "unsubscribe")

Maker = async_sessionmaker[AsyncSession]


class Breaker(Protocol):
    """The slice of Redis the breaker needs."""

    async def exists(self, key: str) -> int: ...
    async def set(self, key: str, value: str, ex: int) -> Any: ...


def backoff_seconds(attempts: int) -> int:
    """Return the wait before the next try after `attempts` failures."""
    return min(30 * 2**attempts, 3600)


@dataclass(frozen=True, slots=True)
class Job:
    """A claimed outbox row."""

    id: uuid.UUID
    op: str
    subscriber_id: uuid.UUID | None
    payload: dict[str, Any]
    attempts: int


@dataclass(slots=True)
class RunStats:
    """Counters of one run; they go to the log, never addresses."""

    done: int = 0
    failed: int = 0
    dead: int = 0
    breaker_open: bool = False


async def requeue_upsert(maker: Maker, subscriber_id: uuid.UUID, now: datetime) -> None:
    """Queue an `upsert` for the reconcile; the key allows one such job per subscriber and day."""
    stmt = (
        insert(Outbox)
        .values(
            op="upsert",
            subscriber_id=subscriber_id,
            idempotency_key=f"upsert:{subscriber_id}:reconcile-{now.date().isoformat()}",
            next_at=now,
        )
        .on_conflict_do_nothing(constraint="uq_outbox_idempotency_key")
    )
    async with maker.begin() as session:
        await session.execute(stmt)


async def release_orphans(maker: Maker, now: datetime) -> None:
    """Put jobs that a crashed run left in `running` back to `pending`."""
    async with maker.begin() as session:
        await session.execute(
            update(Outbox)
            .where(Outbox.state == "running", Outbox.locked_at < now - ORPHAN_AFTER)
            .values(state="pending", locked_at=None)
        )


async def claim(maker: Maker, now: datetime, limit: int = BATCH) -> list[Job]:
    """Lock the due jobs, mark them `running` and return them oldest first."""
    due = (
        select(Outbox.id)
        .where(Outbox.state == "pending", Outbox.next_at <= now)
        .order_by(Outbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    async with maker.begin() as session:
        ids = list((await session.scalars(due)).all())
        if not ids:
            return []
        rows = (
            await session.execute(
                update(Outbox)
                .where(Outbox.id.in_(ids))
                .values(state="running", locked_at=now)
                .returning(
                    Outbox.id,
                    Outbox.op,
                    Outbox.subscriber_id,
                    Outbox.payload,
                    Outbox.attempts,
                    Outbox.created_at,
                )
            )
        ).all()
    ordered = sorted(rows, key=lambda r: r.created_at)
    return [Job(r.id, r.op, r.subscriber_id, dict(r.payload), r.attempts) for r in ordered]


async def finish(maker: Maker, job: Job, now: datetime) -> None:
    """Mark the job done; an erasure job drops its ciphertext now."""
    values: dict[str, Any] = {
        "state": "done",
        "done_at": now,
        "locked_at": None,
        "last_error": None,
    }
    if job.op in CIPHERTEXT_OPS:
        values["payload"] = Outbox.payload.op("-")(text("'emailEnc'"))
    async with maker.begin() as session:
        await session.execute(update(Outbox).where(Outbox.id == job.id).values(**values))


async def fail(maker: Maker, job: Job, error: ListmonkError, now: datetime) -> str:
    """Record a failed try and return the new state (`pending` or `dead`)."""
    attempts = job.attempts + 1
    limit = MAX_ATTEMPTS if error.retryable else MAX_ATTEMPTS_PERMANENT
    state = "dead" if attempts >= limit else "pending"
    reason = f"{error.kind}:{error.status}" if error.status else error.kind
    async with maker.begin() as session:
        await session.execute(
            update(Outbox)
            .where(Outbox.id == job.id)
            .values(
                state=state,
                attempts=attempts,
                next_at=now + timedelta(seconds=backoff_seconds(attempts)),
                locked_at=None,
                last_error=reason[:120],
            )
        )
    return state


async def requeue(maker: Maker, jobs: list[Job]) -> None:
    """Hand unprocessed claimed jobs back without counting a try."""
    if not jobs:
        return
    async with maker.begin() as session:
        await session.execute(
            update(Outbox)
            .where(Outbox.id.in_([j.id for j in jobs]))
            .values(state="pending", locked_at=None)
        )


async def handle_upsert(maker: Maker, port: ListmonkPort, email_key: str, job: Job) -> None:
    """Align the subscriber on Listmonk with the profile; Listmonk's opt-out wins.

    Only a job marked `reconfirmed` (a new double opt-in after an unsubscribe) lifts an old
    blocklist or list opt-out first: the person has just confirmed again on our side.
    """
    if job.subscriber_id is None:
        return
    target = await sync.load_target(maker, job.subscriber_id, email_key)
    if target is None or target.status != "confirmed":
        return
    keys = sync.desired_keys(target.mail_enabled, target.categories)
    ids = await sync.resolve_list_ids(maker, port, keys)
    existing = await port.find_subscriber(target.email)
    if existing is not None and job.payload.get("reconfirmed"):
        await port.resubscribe(existing, set(ids.values()))
        existing = await port.find_subscriber(target.email)
    decision = sync.plan(existing, set(ids.values()))
    if decision.action == "opted_out":
        await sync.mark_unsubscribed(maker, target.subscriber_id)
        return
    if existing is None and not decision.list_ids:
        return
    result = await port.upsert_subscriber(
        target.email, set(decision.list_ids), sync.attribs_of(target)
    )
    await sync.store_listmonk_id(maker, target.subscriber_id, result.id)


async def handle_unsubscribe(maker: Maker, port: ListmonkPort, email_key: str, job: Job) -> None:
    """Blocklist the subscriber on Listmonk so nothing delivers again.

    An erasure job carries the ciphertext because the subscriber row is already wiped.
    """
    email = await _decrypt_payload_email(maker, job.payload, email_key)
    if email is None and job.subscriber_id is not None:
        target = await sync.load_target(maker, job.subscriber_id, email_key)
        email = target.email if target else None
    existing = await port.find_subscriber(email) if email else None
    listmonk_id = existing.id if existing else job.payload.get("listmonkSubscriberId")
    if listmonk_id is not None:
        await port.blocklist(int(listmonk_id))


async def _decrypt_payload_email(
    maker: Maker, payload: dict[str, Any], email_key: str
) -> str | None:
    chiffre = payload.get("emailEnc")
    if not chiffre:
        return None
    raw = base64.b64decode(str(chiffre))
    async with maker() as session:
        value = await session.scalar(select(func.pgp_sym_decrypt(raw, email_key)))
    return str(value) if value else None


async def handle_delete(maker: Maker, port: ListmonkPort, email_key: str, job: Job) -> None:
    """Delete the Listmonk record of an erased subscriber, found by id or by the ciphertext."""
    email = await _decrypt_payload_email(maker, job.payload, email_key)
    found = await port.find_subscriber(email) if email else None
    listmonk_id = found.id if found else job.payload.get("listmonkSubscriberId")
    if listmonk_id is not None:
        await port.delete_subscriber(int(listmonk_id))


async def handle_ensure_list(maker: Maker, port: ListmonkPort, email_key: str, job: Job) -> None:
    """Create the list named in the payload and record its id."""
    key = str(job.payload["key"])
    await sync.register_list(maker, port, key)


HANDLERS = {
    "upsert": handle_upsert,
    "unsubscribe": handle_unsubscribe,
    "delete": handle_delete,
    "ensure_list": handle_ensure_list,
}


async def run_outbox(
    maker: Maker,
    port: ListmonkPort,
    email_key: str,
    *,
    breaker: Breaker | None = None,
    now: datetime | None = None,
) -> RunStats:
    """Process the due jobs once; stop early when the circuit breaker trips."""
    moment = now or utcnow()
    stats = RunStats()
    if breaker is not None and await breaker.exists(BREAKER_KEY):
        stats.breaker_open = True
        return stats
    await release_orphans(maker, moment)
    jobs = await claim(maker, moment)
    streak = 0
    for index, job in enumerate(jobs):
        try:
            await HANDLERS[job.op](maker, port, email_key, job)
        except ListmonkError as error:
            streak += 1
            stats.failed += 1
            if await fail(maker, job, error, moment) == "dead":
                stats.dead += 1
                logger.error("outbox job dead op=%s reason=%s", job.op, error.kind)
            if streak >= BREAKER_FAILURES:
                stats.breaker_open = True
                if breaker is not None:
                    await breaker.set(BREAKER_KEY, "1", ex=BREAKER_SECONDS)
                await requeue(maker, jobs[index + 1 :])
                break
            continue
        streak = 0
        stats.done += 1
        await finish(maker, job, moment)
    logger.info(
        "outbox done=%s failed=%s dead=%s breaker=%s",
        stats.done,
        stats.failed,
        stats.dead,
        stats.breaker_open,
    )
    return stats
