"""Response cache, ETag, invalidation by every lifecycle action, and the rate limit on misses."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.publicapi import cache
from app.shared.antiabuse import get_rate_limiter
from app.shared.ratelimit import InMemoryRateLimiter
from tests.integration.events.harness import Api, future
from tests.integration.publicapi import site_data
from tests.integration.publicapi.conftest import RealPool
from tests.integration.publicapi.site_data import Site

pytestmark = pytest.mark.integration


@pytest.fixture
async def site(api: Api, pool: RealPool) -> Site:
    site_data.configure(api)
    return await site_data.seed(api)


async def snapshot(api: Api, slug: str) -> dict[str, tuple[int, str]]:
    """Fetch every route that shows an event; return status and ETag by route."""
    paths = (
        "/api/public/events",
        f"/api/public/events/{slug}",
        "/api/public/today",
        "/api/public/categories",
        "/api/public/archive",
        f"/e/{slug}",
        "/",
    )
    found = {}
    for path in paths:
        response = await api.request(None, "GET", path)
        found[path] = (response.status_code, response.headers.get("etag", ""))
    return found


INVISIBLE = {"archive", "restore"}


async def test_every_lifecycle_action_shows_at_once(api: Api, site: Site, pool: RealPool) -> None:
    eid, slug = site.ids["cafe"], site.slugs["cafe"]
    steps: list[tuple[str, dict[str, Any]]] = [
        ("cancel", {"reason": "x", "publicReasonCode": "weather"}),
        ("reinstate", {"reason": "doch"}),
        (
            "postpone",
            {
                "reason": "x",
                "publicReasonCode": "room",
                "newStartsAt": future(50).isoformat(),
                "newEndsAt": future(50, 2).isoformat(),
            },
        ),
        ("reinstate", {"reason": "doch"}),
        ("unpublish", {}),
        ("publish", {}),
        ("archive", {}),
        ("restore", {}),
    ]
    before = await snapshot(api, slug)
    version = await cache.current_version(pool)
    for name, body in steps:
        done = await api.act("editor", eid, name, **body)
        assert done.status_code == 200, (name, done.text)
        after = await snapshot(api, slug)
        assert await cache.current_version(pool) > version, name
        version = await cache.current_version(pool)
        if name not in INVISIBLE:
            assert after["/api/public/events"][1] != before["/api/public/events"][1], name
            assert after != before, name
        before = after


async def test_a_poster_change_shows_at_once(api: Api, site: Site, pool: RealPool) -> None:
    url = f"/api/public/events/{site.slugs['movie']}"
    first = await api.request(None, "GET", url)
    assert first.json()["image"]["alt"] == "Ein Filmplakat"
    poster = await api.upload_poster("editor", site.ids["movie"], altText="Neues Plakat")
    assert poster.status_code == 201, poster.text
    pool.jobs.clear()
    assert await api.process_poster(poster.json()["id"], redis=pool) == "clean"
    second = await api.request(None, "GET", url)
    assert second.json()["image"]["alt"] == "Neues Plakat"
    assert second.headers["etag"] != first.headers["etag"]


async def test_etag_304_and_a_stale_etag_gets_a_200(api: Api, site: Site, pool: RealPool) -> None:
    url = f"/api/public/events/{site.slugs['movie']}"
    first = await api.request(None, "GET", url)
    assert first.headers["cache-control"] == "public, max-age=60, stale-while-revalidate=30"
    same = await api.request(None, "GET", url, headers={"If-None-Match": first.headers["etag"]})
    assert same.status_code == 304
    head = await api.request(None, "HEAD", url)
    assert head.status_code == 200 and head.headers["etag"] == first.headers["etag"]
    cached = [key async for key in pool.scan_iter("events:public:resp:*")]
    assert cached
    await api.act(
        "organizer-fsi", site.ids["movie"], "cancel", reason="x", publicReasonCode="other"
    )
    stale = await api.request(None, "GET", url, headers={"If-None-Match": first.headers["etag"]})
    assert stale.status_code == 200 and stale.headers["etag"] != first.headers["etag"]


async def test_errors_are_never_cached(api: Api, site: Site, pool: RealPool) -> None:
    for _ in range(2):
        assert (await api.request(None, "GET", "/api/public/events/nope")).status_code == 404
        assert (await api.request(None, "GET", "/e/nope")).status_code == 404
    assert [key async for key in pool.scan_iter("events:public:resp:*")] == []


async def test_a_redis_outage_is_a_miss_and_never_a_500(
    api: Api, site: Site, pool: RealPool
) -> None:
    await pool.aclose()
    api.app.state.arq_pool = None
    response = await api.request(None, "GET", "/api/public/today")
    assert response.status_code == 200


async def test_only_cache_misses_count_against_the_limit(
    api: Api, site: Site, pool: RealPool
) -> None:
    site_data.configure(api, rl_public_search_per_minute=3, rl_public_per_minute=50)
    api.app.dependency_overrides[get_rate_limiter] = lambda: InMemoryRateLimiter()
    limiter = InMemoryRateLimiter()
    api.app.dependency_overrides[get_rate_limiter] = lambda: limiter
    for _ in range(10):
        assert (
            await api.request(None, "GET", "/api/public/events", params={"q": "kino"})
        ).status_code == 200
    for n in range(2):
        assert (
            await api.request(None, "GET", "/api/public/events", params={"q": f"film{n}"})
        ).status_code == 200
    blocked = await api.request(None, "GET", "/api/public/events", params={"q": "other"})
    assert blocked.status_code == 429 and blocked.json()["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1
    assert (
        await api.request(None, "GET", "/api/public/events", params={"q": "kino"})
    ).status_code == 200
    assert "set-cookie" not in blocked.headers
