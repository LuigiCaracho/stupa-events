"""Edits that change what the view shows bump the feed version, so the feed never lags."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.publicapi import cache
from tests.integration.events.harness import Api
from tests.integration.publicapi.conftest import RealPool
from tests.integration.publicapi.test_snapshot import get
from worker.public_cache import rebuild_public_cache

pytestmark = pytest.mark.integration


async def feed_items(api: Api) -> list[dict]:
    return (await get(api, "/api/public/feed/events")).json()["items"]


async def test_a_private_flag_on_a_venue_shows_in_the_feed_at_once(
    api: Api,
    ctx: dict[str, Any],
    pool: RealPool,
) -> None:
    made = await api.request(
        "editor",
        "POST",
        "/api/admin/venues",
        json={
            "slug": "haus",
            "name": "Haus am Park",
            "address": "Parkweg 1",
            "city": "Reutlingen",
            "publicPrecision": "exact",
        },
    )
    assert made.status_code == 201
    await api.to_state("published", venueId=made.json()["id"])
    await rebuild_public_cache(ctx)
    assert (await feed_items(api))[0]["venue"]["address"] == "Parkweg 1"
    before = await cache.current_version(pool)
    patched = await api.request(
        "editor", "PATCH", f"/api/admin/venues/{made.json()['id']}", json={"isPrivate": True}
    )
    assert patched.status_code == 200
    assert await cache.current_version(pool) == before + 1
    venue = (await feed_items(api))[0]["venue"]
    assert venue is None or "Parkweg" not in str(venue)
    assert "Parkweg" not in (await get(api, "/ics/all.ics")).text


async def test_renaming_an_organization_or_category_shows_in_the_feed_at_once(
    api: Api,
    ctx: dict[str, Any],
    pool: RealPool,
) -> None:
    await api.to_state("published")
    await rebuild_public_cache(ctx)
    org_id = api.org_ids["fsi"]
    original = (await api.sql("SELECT name FROM organization WHERE slug = 'fsi'"))[0][0]
    try:
        renamed = await api.request(
            "editor", "PATCH", f"/api/admin/organizations/{org_id}", json={"name": "Neuer Name eV"}
        )
        assert renamed.status_code == 200
        assert (await feed_items(api))[0]["organization"]["name"] == "Neuer Name eV"
        await rebuild_public_cache(ctx)
        category = await api.request(
            "editor",
            "PATCH",
            f"/api/admin/categories/{api.category_ids['kino']}",
            json={"name": "Lichtspiele"},
        )
        assert category.status_code == 200
        assert "Lichtspiele" in (await get(api, "/ics/all.ics")).text
    finally:
        await api.sql("UPDATE category SET name = 'Kino' WHERE slug = 'kino'")
        await api.sql("UPDATE organization SET name = :n WHERE slug = 'fsi'", n=original)
