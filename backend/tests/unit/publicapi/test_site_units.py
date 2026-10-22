"""Site pieces without a database: clock, parser, cursors, filters, cards, cache, rate limit."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.modules.publicapi import clock, ratelimit, respcache
from app.modules.publicapi.query import cards
from app.modules.publicapi.query.filters import SiteFilters, terms, where
from app.modules.publicapi.query.search import decode_position, encode_offset
from app.modules.search.params import Params
from app.modules.search.words import parse
from app.shared.errors import ValidationProblem, is_cookie_free_path, register_exception_handlers
from app.shared.ratelimit import InMemoryRateLimiter
from tests._support.factories import make_settings
from tests.unit.publicapi.test_public_unit import row

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("day", "start", "end"),
    [
        (date(2026, 3, 29), "2026-03-28T23:00:00+00:00", "2026-03-29T22:00:00+00:00"),
        (date(2026, 10, 25), "2026-10-24T22:00:00+00:00", "2026-10-25T23:00:00+00:00"),
        (date(2026, 1, 5), "2026-01-04T23:00:00+00:00", "2026-01-05T23:00:00+00:00"),
    ],
)
def test_berlin_day_bounds_across_the_clock_changes(day: date, start: str, end: str) -> None:
    assert clock.day_start(day).isoformat() == start
    assert clock.day_end(day).isoformat() == end


def test_month_bounds_and_distance() -> None:
    assert clock.month_bounds(2026, 12)[1] == clock.day_start(date(2027, 1, 1))
    assert clock.month_bounds(2026, 3)[0].isoformat() == "2026-02-28T23:00:00+00:00"
    assert clock.months_between(NOW, 2026, 10) == 0
    assert clock.months_between(NOW, 2028, 10) == 24 and clock.months_between(NOW, 2026, 1) == -9
    assert clock.berlin_date(datetime(2026, 10, 24, 22, 30, tzinfo=UTC)) == date(2026, 10, 25)


def test_the_cookie_free_paths() -> None:
    for path in (
        "/",
        "/suche",
        "/e/x",
        "/k/x",
        "/sitemap.xml",
        "/api/public/events",
        "/ics/all.ics",
    ):
        assert is_cookie_free_path(path), path
    for path in ("/api/auth/me", "/dossiers", "/e", "/suchen", "/api/events"):
        assert not is_cookie_free_path(path), path


def test_cursor_forms_do_not_mix() -> None:
    assert decode_position(None, text=True).offset == 0
    assert decode_position(encode_offset(40), text=True).offset == 40
    for bad in (encode_offset(201), "###", "e30="):
        with pytest.raises(ValidationProblem):
            decode_position(bad, text=True)
    with pytest.raises(ValidationProblem):
        decode_position(encode_offset(5), text=False)


def test_where_renders_every_filter_with_bound_values() -> None:
    filters = SiteFilters(
        now=NOW,
        words=tuple(parse("kino")),
        categories=("kino",),
        organizations=("fsi",),
        start=clock.day_start(date(2026, 11, 1)),
        end=clock.day_end(date(2026, 11, 30)),
    )
    params = Params()
    sql = where(filters, params, terms(filters, params))
    assert "ends_at >=" in sql and "starts_at <" in sql and "category_parent_slug = ANY" in sql
    assert "organization_slug = ANY" in sql and "search_tsv @@" in sql
    assert "kino" not in sql and "fsi" not in sql
    skipped = where(filters, Params(), [], skip=frozenset({"category", "organization", "month"}))
    assert skipped == "true"


def test_default_window_and_past() -> None:
    assert "ends_at >=" in where(SiteFilters(now=NOW), Params(), [])
    past = SiteFilters(now=NOW, past=True)
    assert "ends_at <" in where(past, Params(), []) and past.descending
    ranged = SiteFilters(now=NOW, past=True, start=NOW)
    assert not ranged.descending and "ends_at <" not in where(ranged, Params(), [])


def test_card_and_detail_images_are_relative_and_complete() -> None:
    derivatives = {
        "thumb_400": {"id": "t", "width": 400, "height": 225},
        "card_1200": {"id": "c", "width": 1200, "height": 675},
        "og_1200x630": {"id": "o", "width": 1200, "height": 630},
    }
    item = row(hero_derivatives=derivatives)
    assert cards.card_image(item).url == "/api/public/media/t.webp"  # type: ignore[union-attr]
    assert cards.image_set(item).og.url == "/api/public/media/o.webp"  # type: ignore[union-attr]
    partial = row(hero_derivatives={"thumb_400": derivatives["thumb_400"]})
    assert cards.card_image(partial) is not None and cards.image_set(partial) is None
    assert cards.card_image(row(hero_sha=None, hero_derivatives=None)) is None


def test_card_status_reason_and_path() -> None:
    card = cards.to_card(row(public_status="cancelled", public_reason_code="other"))
    assert card.status_reason is not None and card.status_reason.code == "other"
    assert card.path == "/e/2026-11-05-movienight" and card.venue_name == "Kinosaal"
    assert cards.to_card(row()).status_reason is None


class Redis:
    def __init__(self, version: int | None = 1, fail: bool = False) -> None:
        self.version, self.fail, self.hashes = version, fail, {}

    async def get(self, key: str) -> bytes | None:
        if self.fail:
            raise ConnectionError("down")
        return None if self.version is None else str(self.version).encode()

    async def hgetall(self, key: str) -> dict[Any, Any]:
        return self.hashes.get(key, {})

    def pipeline(self, transaction: bool = True) -> Any:
        outer = self

        class Pipe:
            def __init__(self) -> None:
                self.ops: list[Any] = []

            async def __aenter__(self) -> Any:
                return self

            async def __aexit__(self, *exc: object) -> None:
                return None

            def delete(self, key: str) -> None:
                self.ops.append(("del", key))

            def hset(self, key: str, mapping: dict[str, Any]) -> None:
                outer.hashes[key] = {
                    k.encode(): (v if isinstance(v, bytes) else str(v).encode())
                    for k, v in mapping.items()
                }

            def expire(self, key: str, ttl: int) -> None:
                self.ops.append(("exp", key, ttl))

            async def execute(self) -> None:
                return None

        return Pipe()


def serve_app(redis: Any, calls: list[str], miss: list[str]) -> TestClient:
    app = FastAPI()
    app.state.arq_pool = redis
    register_exception_handlers(app)

    @app.get("/x")
    async def route(request: Request):  # noqa: ANN202
        async def build() -> respcache.Built:
            calls.append("build")
            return respcache.Built(b'{"a":1}', "application/json")

        async def count() -> None:
            miss.append("miss")

        return await respcache.serve(
            request,
            key=respcache.cache_key("/x", {"q": 1}),
            ttl=60,
            cache_control=respcache.SWR,
            build=build,
            on_miss=count,
        )

    return TestClient(app)


def test_the_second_request_is_a_hit_and_only_the_miss_counts() -> None:
    calls: list[str] = []
    miss: list[str] = []
    client = serve_app(Redis(), calls, miss)
    first, second = client.get("/x"), client.get("/x")
    assert (
        first.content == second.content == b'{"a":1}'
        and first.headers["etag"] == second.headers["etag"]
    )
    assert calls == ["build"] and miss == ["miss"]
    assert client.get("/x", headers={"If-None-Match": first.headers["etag"]}).status_code == 304


def test_a_changed_version_makes_the_copy_stale() -> None:
    redis, calls = Redis(), []
    client = serve_app(redis, calls, [])
    client.get("/x")
    redis.version = 2
    client.get("/x")
    assert calls == ["build", "build"]


@pytest.mark.parametrize("redis", [None, Redis(fail=True)])
def test_no_redis_or_a_broken_one_is_a_miss_not_an_error(redis: Any) -> None:
    calls: list[str] = []
    response = serve_app(redis, calls, []).get("/x")
    assert response.status_code == 200 and calls == ["build"]


def test_the_cache_key_ignores_parameter_order_and_distinguishes_paths() -> None:
    assert respcache.cache_key("/a", {"x": 1, "y": 2}) == respcache.cache_key(
        "/a", {"y": 2, "x": 1}
    )
    assert respcache.cache_key("/a", {}) != respcache.cache_key("/b", {})


async def test_the_search_limit_counts_both_keys_and_answers_429() -> None:
    limiter = InMemoryRateLimiter(now=lambda: 100.0)
    settings = make_settings(rl_public_per_minute=5, rl_public_search_per_minute=2)
    await ratelimit.search_limit(limiter, settings, "1.2.3.4")
    await ratelimit.search_limit(limiter, settings, "1.2.3.4")
    with pytest.raises(Exception) as caught:
        await ratelimit.search_limit(limiter, settings, "1.2.3.4")
    assert getattr(caught.value, "status", None) == 429
    assert caught.value.headers["Retry-After"]  # type: ignore[attr-defined]
    await ratelimit.search_limit(limiter, settings, "5.6.7.8")
    for _ in range(2):
        await ratelimit.public_limit(limiter, settings, "9.9.9.9")
