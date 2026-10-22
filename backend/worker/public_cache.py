"""arq job `rebuild_public_cache`: build the feed and every calendar once, store the snapshots.

PLAN 8.1: the worker computes, requests only read. The job reads the version counter before
it reads the view and stores that version with every snapshot, so a change that lands while
it runs makes the snapshots stale instead of silently wrong. It reads the view through the
role `events_public` (never a table), builds the feed items with `textHtml`, the sitemap, the
calendar of all events and the calendar of every category with events in the window and of every
parent category, and writes all snapshots in one `MULTI`. More rows than `PUBLIC_SNAPSHOT_MAX_ROWS`
are logged as `snapshot_too_large`; the API then stays on its live path.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.publicapi import cache, service
from app.modules.publicapi.db import get_public_engine
from app.modules.publicapi.ics.model import IcsRow
from app.modules.publicapi.ics.rows import ics_row, windowed
from app.modules.publicapi.ics.writer import build_calendar
from app.modules.publicapi.schemas import PublicEventOut
from app.modules.publicapi.serving import ICS_TYPE
from app.modules.publicapi.shell import sitemap
from app.settings import Settings, load_settings
from app.shared.timeutil import utcnow

logger = logging.getLogger("worker.public_cache")

_ITEMS = TypeAdapter(list[PublicEventOut])
JSON_TYPE = "application/json"


def _sessionmaker(ctx: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    maker = ctx.get("public_sessionmaker")
    if maker is not None:
        return maker
    return async_sessionmaker(get_public_engine(), expire_on_commit=False, autoflush=False)


def _snapshot(version: int, body: bytes, content_type: str, now: datetime) -> cache.Snapshot:
    return cache.Snapshot(version, cache.etag_of(body), body, content_type, now)


def calendars(
    rows: list[IcsRow], categories: list[tuple[str, str]], parents: set[str], settings: Settings
) -> dict[str, bytes]:
    """Build the calendar bytes by snapshot name for rows that lie in the window.

    Categories with events in the window and every parent category get a calendar of their
    own; any other category is built live when somebody asks for it.
    """
    names = dict(categories)

    def build(selected: list[IcsRow], title: str | None) -> bytes:
        return build_calendar(
            selected,
            base_url=settings.public_base_url,
            uid_domain=settings.ics_uid_domain,
            name=title,
        )

    found: dict[str, bytes] = {cache.ICS_ALL: build(rows, None)}
    used = {s for r in rows for s in (r.category_slug, r.category_parent_slug) if s}
    for slug in sorted((used | parents) & names.keys()):
        mine = [r for r in rows if slug in (r.category_slug, r.category_parent_slug)]
        found[cache.ics_name(slug)] = build(mine, names[slug])
    return found


def _sitemap(rows: list[Any], active: list[str], base: str, now: datetime) -> bytes:
    window = now - sitemap.WINDOW
    events = [(r.slug, r.updated_at) for r in rows if r.ends_at >= window]
    return sitemap.build(base, events, active)


async def rebuild_public_cache(ctx: dict[str, Any], now: datetime | None = None) -> str:
    """Rebuild every snapshot from the view; return the log line.

    Returns:
        `public_cache: rows=<n> snapshots=<m> version=<v>`, or `public_cache: skipped (...)`.
    """
    redis = ctx.get("redis")
    if redis is None:
        return "public_cache: skipped (no redis)"
    settings: Settings = ctx.get("settings") or load_settings()
    moment = now or utcnow()
    version = await cache.current_version(redis)
    async with _sessionmaker(ctx)() as session:
        rows = await service.all_rows(session, settings.public_snapshot_max_rows + 1)
        categories = await service.categories(session)
        parents = await service.parent_slugs(session)
        categories_active = await service.active_category_slugs(session)
    if len(rows) > settings.public_snapshot_max_rows:
        logger.warning("snapshot_too_large rows>%s", settings.public_snapshot_max_rows)
        return "public_cache: skipped (snapshot_too_large)"
    base = settings.public_base_url.rstrip("/")
    items = [service.to_public_event(r, base) for r in rows]
    snapshots = {
        cache.FEED: _snapshot(version, _ITEMS.dump_json(items, by_alias=True), JSON_TYPE, moment)
    }
    snapshots[sitemap.SNAPSHOT] = _snapshot(
        version, _sitemap(rows, categories_active, base, moment), sitemap.SITEMAP_TYPE, moment
    )
    in_window = windowed([ics_row(r) for r in rows], moment)
    for name, body in calendars(in_window, categories, parents, settings).items():
        snapshots[name] = _snapshot(version, body, ICS_TYPE, moment)
    await cache.store(redis, snapshots)
    return f"public_cache: rows={len(rows)} snapshots={len(snapshots)} version={version}"
