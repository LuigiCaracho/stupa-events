"""Target state of a subscriber in Listmonk and the list registry (`listmonk_list`).

`desired_keys` and `plan` are pure. A subscriber who wants mail sits on the list `_all` and on
the list of every category of the profile. Listmonk wins on opt-out: a blocklisted subscriber,
or one who is unsubscribed from every wanted list, becomes `unsubscribed` here too, and a list
the person left is never added again (the unsubscribe is monotonic). The DB helpers open short
transactions of their own, because the role `events_subs` kills a session that idles in a
transaction for more than five seconds while a Listmonk call is under way.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Boolean, Text, column, func, select, table, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.subscriptions.listmonk_port import ListmonkPort, ListmonkSubscriber
from app.modules.subscriptions.models import ListmonkList, Subscriber, SubscriptionProfile
from app.shared.timeutil import utcnow

_CATEGORY = table("public_category_v", column("slug", Text), column("active", Boolean))

ALL_KEY = "_all"
SOURCE = "get-started"

Maker = async_sessionmaker[AsyncSession]


def list_name(key: str) -> str:
    """Return the Listmonk list name of a key (`events-` prefix, `_all` is `events-alle`)."""
    return "events-alle" if key == ALL_KEY else f"events-{key}"


def desired_keys(mail_enabled: bool, categories: list[str]) -> set[str]:
    """Return the list keys a subscriber should sit on; none without mail."""
    return {ALL_KEY, *categories} if mail_enabled else set()


@dataclass(frozen=True, slots=True)
class Plan:
    """What to do with one subscriber: `sync` to `list_ids`, or take Listmonk's opt-out over."""

    action: str
    list_ids: frozenset[int] = frozenset()


def plan(existing: ListmonkSubscriber | None, wanted_ids: set[int]) -> Plan:
    """Decide how to bring Listmonk to the wanted lists without undoing an opt-out."""
    if existing is None:
        return Plan("sync", frozenset(wanted_ids))
    if existing.status == "blocklisted":
        return Plan("opted_out")
    left = {i for i, state in existing.lists.items() if state == "unsubscribed"}
    if wanted_ids and wanted_ids <= left:
        return Plan("opted_out")
    return Plan("sync", frozenset(wanted_ids - left))


@dataclass(frozen=True, slots=True)
class Target:
    """The decrypted state of a subscriber the worker needs for one Listmonk call."""

    subscriber_id: uuid.UUID
    email: str
    status: str
    listmonk_id: int | None
    profile_id: uuid.UUID | None
    categories: list[str]
    mail_enabled: bool
    profile_version: int


def attribs_of(target: Target) -> dict[str, object]:
    """Return the Listmonk attributes: source, profile version, profile id and category slugs."""
    return {
        "source": SOURCE,
        "profile_version": target.profile_version,
        "profil_id": str(target.profile_id) if target.profile_id else None,
        "kategorien": sorted(target.categories),
    }


def _micros(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000)


async def load_target(maker: Maker, subscriber_id: uuid.UUID, email_key: str) -> Target | None:
    """Read and decrypt one subscriber with its profile; None for an erased or missing row."""
    stmt = (
        select(
            func.pgp_sym_decrypt(Subscriber.email_enc, email_key),
            Subscriber.status,
            Subscriber.listmonk_subscriber_id,
            SubscriptionProfile.id,
            SubscriptionProfile.categories,
            SubscriptionProfile.mail_enabled,
            SubscriptionProfile.updated_at,
        )
        .select_from(Subscriber)
        .outerjoin(SubscriptionProfile, SubscriptionProfile.subscriber_id == Subscriber.id)
        .where(Subscriber.id == subscriber_id, Subscriber.email_enc.is_not(None))
    )
    async with maker() as session:
        row = (await session.execute(stmt)).first()
    if row is None:
        return None
    email, status, listmonk_id, profile_id, categories, mail_enabled, updated_at = row
    return Target(
        subscriber_id=subscriber_id,
        email=email,
        status=status,
        listmonk_id=listmonk_id,
        profile_id=profile_id,
        categories=list(categories or []),
        mail_enabled=bool(mail_enabled),
        profile_version=_micros(updated_at) if updated_at else 0,
    )


async def resolve_list_ids(maker: Maker, port: ListmonkPort, keys: set[str]) -> dict[str, int]:
    """Return key to Listmonk id for the wanted lists, creating the missing ones.

    Archived lists are left out: a category that was switched off gets no new subscribers.
    """
    if not keys:
        return {}
    async with maker() as session:
        rows = (await session.execute(select(ListmonkList).where(ListmonkList.key.in_(keys)))).all()
    known = {r[0].key: r[0] for r in rows}
    found: dict[str, int] = {}
    for key in sorted(keys):
        row = known.get(key)
        if row is not None:
            if row.archived_at is None:
                found[key] = row.listmonk_id
            continue
        found[key] = await register_list(maker, port, key)
    return found


async def register_list(maker: Maker, port: ListmonkPort, key: str) -> int:
    """Create the Listmonk list of `key` if needed and record its id."""
    listmonk_id = await port.ensure_list(key, list_name(key))
    stmt = insert(ListmonkList).values(key=key, listmonk_id=listmonk_id, name=list_name(key))
    stmt = stmt.on_conflict_do_update(
        index_elements=[ListmonkList.key],
        set_={"listmonk_id": listmonk_id, "archived_at": None},
    )
    async with maker.begin() as session:
        await session.execute(stmt)
    return listmonk_id


async def mark_unsubscribed(
    maker: Maker, subscriber_id: uuid.UUID, now: datetime | None = None
) -> None:
    """Set a confirmed subscriber to `unsubscribed` and switch its profile mail off."""
    moment = now or utcnow()
    async with maker.begin() as session:
        changed = await session.scalar(
            update(Subscriber)
            .where(Subscriber.id == subscriber_id, Subscriber.status == "confirmed")
            .values(status="unsubscribed", unsubscribed_at=moment, updated_at=moment)
            .returning(Subscriber.id)
        )
        if changed:
            await session.execute(
                update(SubscriptionProfile)
                .where(SubscriptionProfile.subscriber_id == subscriber_id)
                .values(mail_enabled=False, updated_at=moment)
            )


async def store_listmonk_id(maker: Maker, subscriber_id: uuid.UUID, listmonk_id: int) -> None:
    """Remember the Listmonk subscriber id."""
    async with maker.begin() as session:
        await session.execute(
            update(Subscriber)
            .where(Subscriber.id == subscriber_id, Subscriber.status != "erased")
            .values(listmonk_subscriber_id=listmonk_id)
        )


async def sync_category_lists(maker: Maker, port: ListmonkPort) -> dict[str, int]:
    """Create the missing lists of the active categories and archive those of inactive ones.

    Returns:
        Counters `created` and `archived`.
    """
    async with maker() as session:
        categories = {r.slug: r.active for r in (await session.execute(select(_CATEGORY))).all()}
        known = {r[0].key: r[0] for r in (await session.execute(select(ListmonkList))).all()}
    wanted = {ALL_KEY} | {slug for slug, active in categories.items() if active}
    created = 0
    for key in sorted(wanted):
        row = known.get(key)
        if row is None or row.archived_at is not None:
            await register_list(maker, port, key)
            created += 1
    archived = 0
    for key, row in known.items():
        if key not in wanted and row.archived_at is None:
            await port.archive_list(row.listmonk_id)
            async with maker.begin() as session:
                await session.execute(
                    update(ListmonkList).where(ListmonkList.key == key).values(archived_at=utcnow())
                )
            archived += 1
    return {"created": created, "archived": archived}
