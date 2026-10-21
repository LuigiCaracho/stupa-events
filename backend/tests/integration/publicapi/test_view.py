"""The public views: columns equal the allowlist, categories are two levels deep at most."""

from __future__ import annotations

import pytest

from app.modules.publicapi.allowlist import PUBLIC_CATEGORY_COLUMNS, PUBLIC_VIEW_COLUMNS
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def columns(api: Api, view: str) -> tuple[str, ...]:
    rows = await api.sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name = :v "
        "ORDER BY ordinal_position",
        v=view,
    )
    return tuple(r[0] for r in rows)


async def test_public_view_columns(api: Api) -> None:
    assert await columns(api, "public_event_v") == PUBLIC_VIEW_COLUMNS
    assert await columns(api, "public_category_v") == PUBLIC_CATEGORY_COLUMNS


async def test_category_depth(api: Api) -> None:
    deep = await api.sql(
        "SELECT count(*) FROM category c JOIN category p ON p.id = c.parent_id "
        "WHERE p.parent_id IS NOT NULL"
    )
    assert deep == [(0,)]
