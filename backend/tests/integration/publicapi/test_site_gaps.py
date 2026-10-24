"""Edge paths of the site routes: category filters, empty archive, cursors, timeouts, live sitemap."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.exc import DBAPIError

from app.modules.publicapi import cursor as cursors
from app.modules.publicapi import site_router
from tests.integration.events.harness import Api
from tests.integration.publicapi import site_data
from tests.integration.publicapi.conftest import RealPool
from tests.integration.publicapi.site_data import Site

pytestmark = pytest.mark.integration
API = "/api/public"


@pytest.fixture
async def site(api: Api, pool: RealPool) -> Site:
    site_data.configure(api)
    return await site_data.seed(api)


async def ok(api: Api, path: str, **params: Any) -> Any:
    response = await api.request(None, "GET", path, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def test_calendar_and_archive_filter_by_category(api: Api, site: Site) -> None:
    first = (await ok(api, f"{API}/events"))["items"][0]["startsAt"]
    month = datetime.fromisoformat(first).strftime("%Y-%m")
    narrowed = await ok(api, f"{API}/calendar", month=month, category="nonexistent")
    assert narrowed["days"] == []
    archive = await ok(api, f"{API}/archive", category="nonexistent")
    assert archive == {"years": [], "year": None, "items": [], "nextCursor": None}


async def test_archive_pages_with_a_cursor(api: Api, site: Site) -> None:
    plain = await ok(api, f"{API}/archive")
    assert [i["slug"] for i in plain["items"]] == [site.slugs["past"]]
    after = cursors.encode(datetime(2100, 1, 1, tzinfo=UTC), UUID(int=1))
    paged = await ok(api, f"{API}/archive", cursor=after)
    assert paged["year"] == plain["year"]
    beyond = cursors.encode(datetime(1971, 1, 1, tzinfo=UTC), UUID(int=1))
    assert (await ok(api, f"{API}/archive", cursor=beyond))["items"] == []


async def test_a_database_timeout_is_a_503_and_other_errors_are_not_swallowed(
    api: Api, site: Site, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def timeout(*_: Any, **__: Any) -> int:
        raise DBAPIError("select", {}, Exception("canceling statement due to statement timeout"))

    monkeypatch.setattr(site_router.facet_queries, "total", timeout)
    slow = await api.request(None, "GET", f"{API}/events")
    assert slow.status_code == 503 and slow.json()["code"] == "search_unavailable"

    async def broken(*_: Any, **__: Any) -> int:
        raise DBAPIError("select", {}, Exception("something else"))

    monkeypatch.setattr(site_router.facet_queries, "total", broken)
    with pytest.raises(DBAPIError):
        await api.request(None, "GET", f"{API}/events")


async def test_a_failing_cache_read_is_a_miss(
    api: Api, site: Site, pool: RealPool, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def down(*_: Any) -> None:
        raise OSError("down")

    monkeypatch.setattr(pool, "hgetall", down)
    assert (await api.request(None, "GET", f"{API}/today")).status_code == 200
    monkeypatch.setattr(pool, "get", down)
    assert (await api.request(None, "GET", f"{API}/today")).status_code == 200


async def test_the_live_sitemap_asks_the_worker_and_answers_304(
    api: Api, site: Site, pool: RealPool
) -> None:
    first = await api.request(None, "GET", "/sitemap.xml")
    assert first.status_code == 200 and pool.jobs
    again = await api.request(
        None, "GET", "/sitemap.xml", headers={"If-None-Match": first.headers["etag"]}
    )
    assert again.status_code == 304


async def test_a_malformed_category_slug_is_a_404_page(api: Api, site: Site) -> None:
    response = await api.request(None, "GET", "/k/Bad_Slug")
    assert response.status_code == 404 and "noindex" in response.text


@pytest.mark.parametrize(
    "params",
    [
        {"from": "0001-01-01T00:00:00+11:00"},
        {"to": "0653-11-14T12:00:09Z"},
        {"since": "0001-01-01T00:00:00+11:00"},
    ],
)
async def test_the_feed_refuses_instants_the_database_cannot_bind(
    api: Api, site: Site, params: dict[str, str]
) -> None:
    response = await api.request(None, "GET", f"{API}/feed/events", params=params)
    assert response.status_code in (400, 422)


async def test_the_sitemap_comes_from_the_worker_snapshot(
    api: Api, site: Site, ctx: dict[str, Any]
) -> None:
    from worker.public_cache import rebuild_public_cache

    live = await api.request(None, "GET", "/sitemap.xml")
    await rebuild_public_cache(ctx)
    snapped = await api.request(None, "GET", "/sitemap.xml")
    assert snapped.status_code == 200 and snapped.headers["etag"]
    assert b"<urlset" in snapped.content and len(snapped.content) > 0
    assert live.content.count(b"<loc>") == snapped.content.count(b"<loc>")
