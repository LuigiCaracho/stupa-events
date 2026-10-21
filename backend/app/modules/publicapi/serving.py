"""Where the public answers come from: the worker snapshot, else a live read of the view.

`feed_page` and `ics_document` try the Redis snapshot first (`cache.load`); a snapshot that
is missing, stale or unreadable sends the request to the view and asks the worker for a
rebuild. The process keeps the last parsed feed snapshot, keyed by its ETag. Failures of the
cache are never errors: the live path is always correct, only slower.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.pipeline.actions import request_rebuild
from app.modules.publicapi import cache, selection, service
from app.modules.publicapi.ics.rows import ics_row, window_bounds, windowed
from app.modules.publicapi.ics.writer import build_calendar
from app.modules.publicapi.schemas import PublicEventOut
from app.modules.publicapi.service import FeedQuery
from app.settings import Settings

_ITEMS = TypeAdapter(list[PublicEventOut])
_memo: dict[str, tuple[str, list[PublicEventOut]]] = {}
ICS_TYPE = "text/calendar; charset=utf-8"


@dataclass(frozen=True, slots=True)
class FeedPage:
    """One page of the feed with the time it was generated."""

    items: list[PublicEventOut]
    next_cursor: str | None
    generated_at: datetime


@dataclass(frozen=True, slots=True)
class IcsDocument:
    """A calendar body with its ETag."""

    body: bytes
    etag: str


def _parsed(snap: cache.Snapshot) -> list[PublicEventOut]:
    cached = _memo.get(cache.FEED)
    if cached is not None and cached[0] == snap.etag:
        return cached[1]
    items = _ITEMS.validate_json(snap.body)
    _memo[cache.FEED] = (snap.etag, items)
    return items


async def feed_page(
    redis: Any, session: AsyncSession, query: FeedQuery, settings: Settings
) -> FeedPage:
    """Serve one feed page from the snapshot, or live from the view."""
    snap = await cache.load(
        redis, cache.FEED, max_age_seconds=settings.public_snapshot_max_age_seconds
    )
    if snap is not None:
        shown, next_cursor = selection.page(_parsed(snap), query)
        return FeedPage(shown, next_cursor, snap.generated_at)
    base = settings.public_base_url.rstrip("/")
    items, next_cursor = await service.feed_items(session, query, base)
    if redis is not None:
        await request_rebuild(redis)
    return FeedPage(items, next_cursor, datetime.now(UTC))


async def ics_document(
    redis: Any,
    session: AsyncSession,
    name: str,
    category: str | None,
    settings: Settings,
    now: datetime | None = None,
) -> IcsDocument | None:
    """Serve a calendar from the snapshot, or build it live; `None` for an unknown category."""
    snap = await cache.load(redis, name, max_age_seconds=settings.public_snapshot_max_age_seconds)
    if snap is not None:
        return IcsDocument(snap.body, snap.etag)
    title = None
    if category is not None:
        known = await service.category_name(session, category)
        if known is None:
            return None
        title = known
    moment = now or datetime.now(UTC)
    rows = windowed(
        [ics_row(r) for r in await service.ics_rows(session, category, window_bounds(moment))],
        moment,
    )
    body = build_calendar(
        rows,
        base_url=settings.public_base_url,
        uid_domain=settings.ics_uid_domain,
        name=title,
    )
    if redis is not None:
        await request_rebuild(redis)
    return IcsDocument(body, cache.etag_of(body))
