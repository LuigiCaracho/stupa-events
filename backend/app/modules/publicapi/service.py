"""Feed and media lookups on the view `public_event_v`, and the row-to-item mapping.

The view is the only thing the public role can read; it already filters the state, the image
rule and the location rules, so a row here is public by construction. This module builds
`PublicEventOut` field by field (no ORM, no `model_dump` of a row), selects items live from
the view with the filters of contract 9.2, and hashes items for the ETag. The same filters
exist in Python (`select.py`) for the worker snapshot; `test_snapshot_matches_live` keeps
the two equal.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import Boolean, Date, DateTime, Integer, Row, String, Text, Uuid, and_, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import column, func, table

from app.modules.publicapi import cursor as cursors
from app.modules.publicapi.schemas import (
    FeedOut,
    PublicCategory,
    PublicEventOut,
    PublicFormat,
    PublicImage,
    PublicOrganization,
    PublicStatusReason,
    PublicVenue,
)
from app.modules.publicapi.textsafe import text_html

MEDIA_PATH = "/api/public/media"
CARD_VARIANT = "card_1200"
PRIVATE_VENUE = "Treffpunkt auf Anfrage"

PUBLIC_EVENT_V = table(
    "public_event_v",
    column("id", Uuid),
    column("slug", Text),
    column("title", Text),
    column("summary", Text),
    column("starts_at", DateTime(timezone=True)),
    column("ends_at", DateTime(timezone=True)),
    column("all_day", Boolean),
    column("tzid", Text),
    column("public_status", String),
    column("organization_id", Uuid),
    column("organization_slug", Text),
    column("organization_name", Text),
    column("organization_short", Text),
    column("venue_text", Text),
    column("category_slug", Text),
    column("category_name", Text),
    column("category_kind", Text),
    column("hero_sha", Text),
    column("hero_derivatives", JSONB),
    column("hero_alt", Text),
    column("hero_credit", Text),
    column("updated_at", DateTime(timezone=True)),
    column("public_reason_code", Text),
    column("public_reason_text", Text),
    column("starts_on", Date),
    column("ends_on", Date),
    column("public_seq", Integer),
    column("category_parent_slug", Text),
    column("category_parent_name", Text),
    column("category_parent_kind", Text),
    column("format_slug", Text),
    column("format_title", Text),
    column("venue_name", Text),
    column("venue_address", Text),
    column("venue_city", Text),
    column("ticket_url", Text),
    column("website_url", Text),
    column("cost_text", Text),
    column("description_md", Text),
)
V = PUBLIC_EVENT_V.c


@dataclass(frozen=True, slots=True)
class FeedQuery:
    """Filters of `GET /api/public/feed/events` (contract 9.2)."""

    start: datetime | None = None
    end: datetime | None = None
    since: datetime | None = None
    category: str | None = None
    organization: str | None = None
    cursor: cursors.Cursor | None = None
    limit: int = 100


def _image(row: Row[Any], base_url: str) -> PublicImage | None:
    derivative = (row.hero_derivatives or {}).get(CARD_VARIANT)
    if row.hero_sha is None or derivative is None:
        return None
    return PublicImage(
        url=f"{base_url}{MEDIA_PATH}/{derivative['id']}.webp",
        width=derivative["width"],
        height=derivative["height"],
        alt=row.hero_alt or "",
        credit=row.hero_credit or "",
    )


def _categories(row: Row[Any]) -> list[PublicCategory]:
    found = []
    if row.category_slug:
        found.append(
            PublicCategory(slug=row.category_slug, name=row.category_name, kind=row.category_kind)
        )
    if row.category_parent_slug:
        found.append(
            PublicCategory(
                slug=row.category_parent_slug,
                name=row.category_parent_name,
                kind=row.category_parent_kind,
            )
        )
    return found


def _venue(row: Row[Any]) -> PublicVenue | None:
    if row.venue_name is None:
        return None
    return PublicVenue(name=row.venue_name, address=row.venue_address, city=row.venue_city)


def to_public_event(row: Row[Any], base_url: str) -> PublicEventOut:
    """Build the public shape of one view row, field by field."""
    return PublicEventOut(
        id=row.id,
        slug=row.slug,
        title=row.title,
        summary=row.summary,
        starts_at=row.starts_at.astimezone(UTC),
        ends_at=row.ends_at.astimezone(UTC),
        all_day=row.all_day,
        starts_on=row.starts_on,
        ends_on=row.ends_on,
        tzid=row.tzid,
        status=row.public_status,
        organization=PublicOrganization(
            id=row.organization_id,
            slug=row.organization_slug,
            name=row.organization_name,
            short=row.organization_short,
        ),
        venue_text=row.venue_text,
        venue=_venue(row),
        status_reason=(
            None
            if row.public_status == "scheduled"
            else PublicStatusReason(code=row.public_reason_code, text=row.public_reason_text)
        ),
        categories=_categories(row),
        format=(
            PublicFormat(slug=row.format_slug, title=row.format_title) if row.format_slug else None
        ),
        image=_image(row, base_url),
        ticket_url=row.ticket_url,
        website_url=row.website_url,
        cost_text=row.cost_text,
        text_html=text_html(row.description_md),
        sequence=row.public_seq,
        updated_at=row.updated_at.astimezone(UTC),
        url=f"{base_url}/e/{row.slug}",
    )


def _conditions(query: FeedQuery) -> list[Any]:
    found: list[Any] = []
    if query.start is not None:
        found.append(V.ends_at >= query.start)
    if query.end is not None:
        found.append(V.starts_at <= query.end)
    if query.since is not None:
        found.append(V.updated_at >= query.since)
    if query.category:
        found.append(
            or_(V.category_slug == query.category, V.category_parent_slug == query.category)
        )
    if query.organization:
        found.append(V.organization_slug == query.organization)
    if query.cursor is not None:
        after, ident = query.cursor.starts_at, query.cursor.id
        found.append(or_(V.starts_at > after, and_(V.starts_at == after, V.id > ident)))
    return found


async def feed_items(
    session: AsyncSession, query: FeedQuery, base_url: str
) -> tuple[list[PublicEventOut], str | None]:
    """Read one page live from the view; the second value is the cursor of the next page."""
    statement = select(PUBLIC_EVENT_V).where(*_conditions(query))
    rows = (
        await session.execute(statement.order_by(V.starts_at, V.id).limit(query.limit + 1))
    ).all()
    items = [to_public_event(row, base_url) for row in rows[: query.limit]]
    more = len(rows) > query.limit
    return items, cursors.encode(items[-1].starts_at, items[-1].id) if more else None


async def all_rows(session: AsyncSession, limit: int) -> list[Row[Any]]:
    """Read every public row (at most `limit`) for the snapshot builder, ordered like the feed."""
    statement = select(PUBLIC_EVENT_V).order_by(V.starts_at, V.id).limit(limit)
    return list((await session.execute(statement)).all())


_ITEMS = TypeAdapter(list[PublicEventOut])


def items_etag(items: Sequence[PublicEventOut], next_cursor: str | None = None) -> str:
    """Return a strong ETag over the items and the next cursor (not the generation time)."""
    body = _ITEMS.dump_json(list(items), by_alias=True) + (next_cursor or "").encode()
    return f'"{hashlib.sha256(body).hexdigest()[:32]}"'


_FEED = TypeAdapter(FeedOut)


def feed_json(items: list[PublicEventOut], now: datetime, next_cursor: str | None = None) -> bytes:
    """Serialize the feed envelope of schema 2 with the generation time `now`."""
    feed = FeedOut(schema=2, generated_at=now.astimezone(UTC), next_cursor=next_cursor, items=items)
    return _FEED.dump_json(feed, by_alias=True)


async def derivative_is_public(
    session: AsyncSession, sha_prefix: str, variant: str, derivative_id: str
) -> bool:
    """Tell if the derivative `derivative_id` is a variant of the poster of a public event."""
    rows = (
        await session.execute(
            select(V.hero_derivatives).where(func.left(V.hero_sha, len(sha_prefix)) == sha_prefix)
        )
    ).scalars()
    return any(
        (derivatives or {}).get(variant, {}).get("id") == derivative_id for derivatives in rows
    )


PUBLIC_CATEGORY_V = table(
    "public_category_v",
    column("slug", Text),
    column("name", Text),
    column("kind", Text),
    column("parent_slug", Text),
)


async def category_name(session: AsyncSession, slug: str) -> str | None:
    """Return the name of a category, or `None` when no category has this slug."""
    stmt = select(PUBLIC_CATEGORY_V.c.name).where(PUBLIC_CATEGORY_V.c.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()


async def categories(session: AsyncSession) -> list[tuple[str, str]]:
    """Return `(slug, name)` of every category for the snapshot builder."""
    stmt = select(PUBLIC_CATEGORY_V.c.slug, PUBLIC_CATEGORY_V.c.name).order_by(
        PUBLIC_CATEGORY_V.c.slug
    )
    return [(slug, name) for slug, name in (await session.execute(stmt)).all()]


async def ics_rows(
    session: AsyncSession,
    category: str | None,
    window: tuple[datetime, datetime],
) -> list[Row[Any]]:
    """Read the rows of one calendar live: those ending after `window[0]`, starting before
    `window[1]`, of all categories or of one category and its children."""
    statement = select(PUBLIC_EVENT_V).where(V.ends_at >= window[0], V.starts_at <= window[1])
    if category is not None:
        statement = statement.where(
            or_(V.category_slug == category, V.category_parent_slug == category)
        )
    return list((await session.execute(statement.order_by(V.starts_at, V.id))).all())


async def parent_slugs(session: AsyncSession) -> set[str]:
    """Return the slugs of the categories that have children."""
    stmt = select(PUBLIC_CATEGORY_V.c.parent_slug).where(
        PUBLIC_CATEGORY_V.c.parent_slug.is_not(None)
    )
    return {slug for (slug,) in (await session.execute(stmt)).all()}
