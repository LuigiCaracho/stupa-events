"""Daily garbage collection: unreferenced Markdown images and old read notifications.

`gc_media` works in two phases so a late reference saves an image. An image older than
7 days without a `media_ref` gets `gc_marked_at`; a mark older than 1 day on an image that
is still unreferenced deletes the object first and the row second (a storage error leaves
the row for the next run); an image that is referenced again loses its mark. A reference
from an old document revision counts, so such an image is never deleted. At most `BATCH`
images per phase; one run per day (`gc_media:<yyyymmdd>`). `gc_notifications` deletes read
notifications after 90 days.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, DateTime, Text, Uuid, delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import column, table

from app.db import get_sessionmaker
from app.modules.files.storage import ObjectStorage
from app.modules.notifications.models import Notification
from app.shared.timeutil import utcnow

logger = logging.getLogger("worker.gc")

BATCH = 200
MARK_AFTER = timedelta(days=7)
SWEEP_AFTER = timedelta(days=1)
NOTIFICATION_KEEP = timedelta(days=90)
KEY_TTL_SECONDS = 24 * 3600

_IMAGE = table(
    "markdown_image",
    column("id", Uuid),
    column("storage_key", Text),
    column("created_at", DateTime(timezone=True)),
    column("gc_marked_at", DateTime(timezone=True)),
)
_REF = table("media_ref", column("image_id", Uuid))
_referenced = exists().where(_REF.c.image_id == _IMAGE.c.id)


def _sessionmaker(ctx: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    maker = ctx.get("gc_sessionmaker")
    return maker if maker is not None else get_sessionmaker()


def _count(result: Any) -> int:
    return cast(CursorResult[Any], result).rowcount or 0


async def _unmark_referenced(session: AsyncSession) -> int:
    result = await session.execute(
        update(_IMAGE)
        .where(_IMAGE.c.gc_marked_at.is_not(None), _referenced)
        .values(gc_marked_at=None)
    )
    return _count(result)


async def _mark_orphans(session: AsyncSession, now: Any) -> int:
    ids = (
        select(_IMAGE.c.id)
        .where(
            _IMAGE.c.created_at < now - MARK_AFTER,
            _IMAGE.c.gc_marked_at.is_(None),
            ~_referenced,
        )
        .limit(BATCH)
    )
    result = await session.execute(
        update(_IMAGE).where(_IMAGE.c.id.in_(ids)).values(gc_marked_at=now)
    )
    return _count(result)


async def _sweep_marked(session: AsyncSession, storage: ObjectStorage, now: Any) -> int:
    rows = (
        await session.execute(
            select(_IMAGE.c.id, _IMAGE.c.storage_key)
            .where(_IMAGE.c.gc_marked_at < now - SWEEP_AFTER, ~_referenced)
            .limit(BATCH)
        )
    ).all()
    deleted = 0
    for image_id, key in rows:
        if not await _drop(session, storage, image_id, key):
            continue
        deleted += 1
    return deleted


async def _drop(session: AsyncSession, storage: ObjectStorage, image_id: UUID, key: str) -> bool:
    locked = await session.scalar(
        select(_IMAGE.c.id).where(_IMAGE.c.id == image_id, ~_referenced).with_for_update()
    )
    if locked is None:
        return False
    try:
        await storage.remove(key)
    except Exception:  # noqa: BLE001 - keep the row, the next run retries
        logger.warning("gc_media: storage error, row kept (image=%s)", image_id)
        return False
    result = await session.execute(delete(_IMAGE).where(_IMAGE.c.id == image_id, ~_referenced))
    return _count(result) > 0


async def _claim_day(ctx: dict[str, Any], day: str) -> bool:
    redis = ctx.get("redis")
    if redis is None:
        return True
    return bool(await redis.set(f"gc_media:{day}", "1", nx=True, ex=KEY_TTL_SECONDS))


async def gc_media(ctx: dict[str, Any]) -> str:
    """Mark, sweep and unmark unreferenced Markdown images.

    Returns:
        The log line, or `"skipped"` when today's run already happened.
    """
    now = utcnow()
    if not await _claim_day(ctx, now.strftime("%Y%m%d")):
        return "skipped"
    storage: ObjectStorage = ctx["object_storage"]
    async with _sessionmaker(ctx)() as session:
        unmarked = await _unmark_referenced(session)
        swept = await _sweep_marked(session, storage, now)
        marked = await _mark_orphans(session, now)
        await session.commit()
    line = f"gc_media: marked={marked} swept={swept} unmarked={unmarked}"
    logger.info(line)
    return line


async def gc_notifications(ctx: dict[str, Any]) -> str:
    """Delete read notifications older than 90 days."""
    cutoff = utcnow() - NOTIFICATION_KEEP
    async with _sessionmaker(ctx)() as session:
        result = await session.execute(
            delete(Notification).where(
                Notification.read_at.is_not(None), Notification.read_at < cutoff
            )
        )
        await session.commit()
    line = f"gc_notifications: deleted={_count(result)}"
    logger.info(line)
    return line
