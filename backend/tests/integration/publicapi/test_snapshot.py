"""The worker snapshot in Redis: equal to the live read, rebuilt on change, never a 500."""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from app.modules.publicapi import cache
from tests._support.factories import make_settings
from tests.integration.events.harness import Api, future
from tests.integration.publicapi.conftest import RealPool
from worker.public_cache import rebuild_public_cache

pytestmark = pytest.mark.integration


class BrokenPool:
    """Every call fails, like a Redis that is down."""

    def __getattr__(self, name: str) -> Any:
        async def fail(*args: Any, **kwargs: Any) -> None:
            raise ConnectionError("redis is down")

        return fail


async def get(api: Api, path: str, **kw: Any):  # noqa: ANN201
    return await api.request(None, "GET", path, **kw)


def strip_time(body: bytes) -> dict:
    data = json.loads(body)
    data.pop("generatedAt")
    return data


async def three_events(api: Api) -> list[dict]:
    return [
        await api.to_state(
            "live",
            title=f"Termin {i}",
            startsAt=future(10 + i).isoformat(),
            endsAt=future(10 + i, 2).isoformat(),
            primaryCategoryId=api.category_ids["kino" if i % 2 == 0 else "get-together"],
        )
        for i in range(3)
    ]


async def test_snapshot_matches_live(api: Api, ctx: dict[str, Any], pool: RealPool) -> None:
    await three_events(api)
    live_feed = (await get(api, "/api/public/feed/events", params={"limit": 2})).content
    live_all = (await get(api, "/ics/all.ics")).content
    live_kino = (await get(api, "/ics/k/kino.ics")).content
    assert not await pool.exists(f"{cache.SNAPSHOT_PREFIX}feed")
    line = await rebuild_public_cache(ctx)
    assert "rows=3" in line and "snapshots=" in line
    snap_feed = (await get(api, "/api/public/feed/events", params={"limit": 2})).content
    assert strip_time(snap_feed) == strip_time(live_feed)
    assert (await get(api, "/ics/all.ics")).content == live_all
    assert (await get(api, "/ics/k/kino.ics")).content == live_kino
    keys = {
        k.decode().removeprefix(cache.SNAPSHOT_PREFIX)
        async for k in pool.scan_iter(f"{cache.SNAPSHOT_PREFIX}*")
    }
    assert {"feed", "ics:all", "ics:k:kino", "ics:k:get-together"} <= keys
    ttl = await pool.ttl(f"{cache.SNAPSHOT_PREFIX}feed")
    assert 0 < ttl <= cache.SNAPSHOT_TTL_SECONDS


async def test_a_fresh_snapshot_is_what_the_api_serves(api: Api, ctx: dict[str, Any]) -> None:
    await three_events(api)
    await rebuild_public_cache(ctx)
    await api.sql("UPDATE event SET title = 'Heimlich geändert'")
    served = (await get(api, "/api/public/feed/events")).json()
    assert all(i["title"].startswith("Termin") for i in served["items"])


async def test_invalidate_rebuilds(api: Api, ctx: dict[str, Any], pool: RealPool) -> None:
    first = await api.to_state("live", title="Erster")
    await rebuild_public_cache(ctx)
    etag_one = (await get(api, "/api/public/feed/events")).headers["etag"]
    pool.jobs.clear()
    second = await api.to_state("approved", title="Zweiter")
    live = await api.fire("editor", second["id"], "T05")
    assert live.status_code == 200
    assert ("rebuild_public_cache", {"_job_id": "public_cache"}) in pool.jobs
    stale = await get(api, "/api/public/feed/events")
    assert stale.headers["etag"] != etag_one and len(stale.json()["items"]) == 2
    await rebuild_public_cache(ctx)
    fresh = await get(api, "/api/public/feed/events")
    assert fresh.headers["etag"] == stale.headers["etag"] and len(fresh.json()["items"]) == 2
    old = await get(api, "/api/public/feed/events", headers={"If-None-Match": etag_one})
    assert old.status_code == 200
    assert first["id"] in str(fresh.json())


async def test_a_stale_version_is_not_served(api: Api, ctx: dict[str, Any], pool: RealPool) -> None:
    await three_events(api)
    await rebuild_public_cache(ctx)
    await api.sql("UPDATE event SET title = 'Neu'")
    await pool.incr("events:feed:version")
    assert all(
        i["title"] == "Neu" for i in (await get(api, "/api/public/feed/events")).json()["items"]
    )
    assert any(job[0] == "rebuild_public_cache" for job in pool.jobs)
    ics = (await get(api, "/ics/all.ics")).content.decode()
    assert "SUMMARY:Neu" in ics


async def test_an_old_snapshot_is_not_served(api: Api, ctx: dict[str, Any], pool: RealPool) -> None:
    await three_events(api)
    await rebuild_public_cache(ctx)
    await pool.hset(f"{cache.SNAPSHOT_PREFIX}feed", "generatedAt", "2020-01-01T00:00:00+00:00")  # type: ignore[misc]
    await api.sql("UPDATE event SET title = 'Live gelesen'")
    assert all(
        i["title"] == "Live gelesen"
        for i in (await get(api, "/api/public/feed/events")).json()["items"]
    )


async def test_redis_down_falls_back_live(api: Api) -> None:
    await api.to_state("live")
    api.app.state.arq_pool = BrokenPool()
    feed = await get(api, "/api/public/feed/events")
    assert feed.status_code == 200 and len(feed.json()["items"]) == 1
    ics = await get(api, "/ics/all.ics")
    assert ics.status_code == 200 and b"BEGIN:VEVENT" in ics.content
    assert (await get(api, "/ics/k/kino.ics")).status_code == 200


async def test_too_many_rows_leave_the_api_on_the_live_path(
    api: Api, ctx: dict[str, Any], pool: RealPool
) -> None:
    await three_events(api)
    ctx["settings"] = make_settings(public_snapshot_max_rows=2)
    assert "snapshot_too_large" in await rebuild_public_cache(ctx)
    assert not await pool.exists(f"{cache.SNAPSHOT_PREFIX}feed")  # type: ignore[misc]
    assert len((await get(api, "/api/public/feed/events")).json()["items"]) == 3


async def test_the_job_skips_without_redis(ctx: dict[str, Any]) -> None:
    assert "no redis" in await rebuild_public_cache({**ctx, "redis": None})


async def test_poster_promotion_bumps_the_version_and_queues_a_rebuild(
    api: Api, ctx: dict[str, Any], pool: RealPool
) -> None:
    from tests.integration.dossier.helpers import clean_poster, live_event

    event = await live_event(api)
    await rebuild_public_cache(ctx)
    pool.jobs.clear()
    before = await cache.current_version(pool)
    replacement = await api.request(
        "editor",
        "POST",
        f"/api/events/{event['id']}/poster",
        data={"altText": "Neu", "credit": "Foto: Bo", "rightsBasis": "own_work"},
        files={
            "file": (
                "neu.png",
                __import__("tests._support.factories", fromlist=["x"]).png_bytes(color="#aa3366"),
                "image/png",
            )
        },
    )
    assert replacement.status_code == 201, replacement.text
    from app.modules.dossier.derive import derive_poster
    from app.modules.dossier.previews import build_preview
    from app.modules.dossier.promote import promote_poster
    from tests.integration.events.harness import CleanScanner
    from worker.scan import scan_attachment

    wctx = {
        "settings": make_settings(),
        "scanner": CleanScanner(),
        "object_storage": api.private,
        "public_storage": api.public,
        "files_sessionmaker": api.maker,
        "redis": pool,
    }
    attachment_id = replacement.json()["id"]
    assert await scan_attachment(wctx, attachment_id) == "clean"
    await derive_poster(wctx, attachment_id)
    await build_preview(wctx, attachment_id)
    assert await promote_poster(wctx, attachment_id) == "promoted"
    assert await cache.current_version(pool) == before + 1
    assert any(job[0] == "rebuild_public_cache" for job in pool.jobs)
    assert clean_poster


async def test_the_job_reads_through_the_public_engine_by_default(
    api: Api, ctx: dict[str, Any], db_roles: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from worker import public_cache

    await three_events(api)
    engine = create_async_engine(db_roles[1].replace("postgresql+psycopg", "postgresql+asyncpg"))
    monkeypatch.setattr(public_cache, "get_public_engine", lambda: engine)
    without_maker = {k: v for k, v in ctx.items() if k != "public_sessionmaker"}
    assert "rows=3" in await rebuild_public_cache(without_maker)
    await engine.dispose()
