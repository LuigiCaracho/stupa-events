"""Feed and media lookups on the view `public_event_v`.

The view is the only thing the public role can read. It already filters the state and the
image rule, so a row here is public by construction. This module builds `PublicEventOut`
field by field and hashes the items for the ETag.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import Boolean, DateTime, Row, String, Text, Uuid, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import column, func, table

from app.modules.publicapi.schemas import (
    FeedOut,
    PublicCategory,
    PublicEventOut,
    PublicImage,
    PublicOrganization,
)

MEDIA_PATH = "/api/public/media"
CARD_VARIANT = "card_1200"

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
)
V = PUBLIC_EVENT_V.c


@dataclass(frozen=True, slots=True)
class FeedQuery:
    """Filters of `GET /api/public/feed/events`."""

    start: datetime | None = None
    end: datetime | None = None
    category: str | None = None
    organization: str | None = None
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
        tzid=row.tzid,
        status=row.public_status,
        organization=PublicOrganization(
            id=row.organization_id,
            slug=row.organization_slug,
            name=row.organization_name,
            short=row.organization_short,
        ),
        venue_text=row.venue_text,
        categories=(
            [PublicCategory(slug=row.category_slug, name=row.category_name, kind=row.category_kind)]
            if row.category_slug
            else []
        ),
        image=_image(row, base_url),
        url=f"{base_url}/e/{row.slug}",
    )


async def feed_items(
    session: AsyncSession, query: FeedQuery, base_url: str
) -> list[PublicEventOut]:
    """Read the public events by start time and id, filtered by `query`."""
    statement = select(PUBLIC_EVENT_V)
    if query.start is not None:
        statement = statement.where(V.ends_at >= query.start)
    if query.end is not None:
        statement = statement.where(V.starts_at <= query.end)
    if query.category:
        statement = statement.where(V.category_slug == query.category)
    if query.organization:
        statement = statement.where(V.organization_slug == query.organization)
    statement = statement.order_by(V.starts_at, V.id).limit(query.limit)
    rows = (await session.execute(statement)).all()
    return [to_public_event(row, base_url) for row in rows]


_ITEMS = TypeAdapter(list[PublicEventOut])


def items_etag(items: Sequence[PublicEventOut]) -> str:
    """Return a strong ETag over the items (the generation time is not part of it)."""
    body = _ITEMS.dump_json(list(items), by_alias=True)
    return f'"{hashlib.sha256(body).hexdigest()[:32]}"'


_FEED = TypeAdapter(FeedOut)


def feed_json(items: list[PublicEventOut], now: datetime) -> bytes:
    """Serialize the feed envelope of schema 2 with the generation time `now`."""
    feed = FeedOut(schema=2, generated_at=now.astimezone(UTC), items=items)
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
