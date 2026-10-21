"""The feed filters in Python: the worker snapshot is filtered here, the live path in SQL.

`matches` and `page` must give the same items as `service.feed_items` for the same query;
`test_snapshot_matches_live` compares them on the same rows.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.modules.publicapi import cursor as cursors
from app.modules.publicapi.schemas import PublicEventOut
from app.modules.publicapi.service import FeedQuery


def matches(item: PublicEventOut, query: FeedQuery) -> bool:
    """Tell if an item passes every filter of the query (cursor included)."""
    cursor = query.cursor
    checks = (
        query.start is None or item.ends_at >= query.start,
        query.end is None or item.starts_at <= query.end,
        query.since is None or item.updated_at >= query.since,
        not query.category or any(c.slug == query.category for c in item.categories),
        not query.organization or item.organization.slug == query.organization,
        cursor is None or (item.starts_at, item.id) > (cursor.starts_at, cursor.id),
    )
    return all(checks)


def page(
    items: Sequence[PublicEventOut], query: FeedQuery
) -> tuple[list[PublicEventOut], str | None]:
    """Return one page of the sorted items and the cursor of the next page."""
    found = [item for item in items if matches(item, query)]
    shown = found[: query.limit]
    more = len(found) > query.limit
    return shown, cursors.encode(shown[-1].starts_at, shown[-1].id) if more else None
