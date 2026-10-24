"""Canary of the subscription flows: an address and the tokens appear nowhere they must not.

One person signs up with mail, confirms, asks for the magic link and fetches the profile
calendar, all against a real Redis (rate limits, replay guard, snapshots). Afterwards the
address and every token are searched in the public feed, every calendar, the sitemap, the
logs of our own code, the audit chain and every Redis key and value. The only places that may
hold them: the ciphertext column (encrypted), the digests (hashes), the mail job body.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from app.shared.altcha import RedisReplayGuard
from app.shared.ratelimit import RedisRateLimiter
from tests.integration.subscriptions.subs_harness import (
    SubsApi,
    api,
    clean_events,
    db_roles,
    link_of,
    subs,
    subs_url,
)

__fixtures__ = (api, clean_events, db_roles, subs, subs_url)
pytestmark = pytest.mark.integration
ADDRESS = "canary-person@example.org"
TOKEN_URL = re.compile(r"/ics/p/([A-Za-z0-9_-]{43})\.ics")


@pytest_asyncio.fixture
async def redis(redis_url: str):  # noqa: ANN201
    client = Redis.from_url(redis_url)
    await client.flushall()
    yield client
    await client.flushall()
    await client.aclose()


async def everything_in(redis: Any) -> str:
    seen: list[str] = []
    async for key in redis.scan_iter("*"):
        seen.append(key.decode())
        kind = (await redis.type(key)).decode()
        if kind == "string":
            seen.append((await redis.get(key)).decode("utf-8", "replace"))
        elif kind == "hash":
            for field, value in (await redis.hgetall(key)).items():
                seen += [field.decode(), value.decode("utf-8", "replace")]
        elif kind == "zset":
            seen += [m.decode() for m in await redis.zrange(key, 0, -1)]
        elif kind == "list":
            seen += [m.decode("utf-8", "replace") for m in await redis.lrange(key, 0, -1)]
    return "\n".join(seen)


async def test_neither_address_nor_token_leaks(
    subs: SubsApi, redis: Redis, caplog: pytest.LogCaptureFixture
) -> None:
    api = subs.api
    api.app.state.arq_pool = redis
    subs.use_limiter(RedisRateLimiter(redis))
    subs.require_altcha(RedisReplayGuard(redis), solve=True)
    await api.to_state(
        "published", title="Canary-Party", primaryCategoryId=api.category_ids["party"]
    )
    tokens: list[str] = []
    with caplog.at_level(logging.DEBUG):
        created = await subs.subscribe(email=ADDRESS)
        ics = TOKEN_URL.search(created.json()["profile"]["icsUrl"])
        assert ics is not None
        tokens.append(ics[1])
        _, confirm = link_of(subs.queue.sent[-1])
        tokens.append(confirm)
        await subs.post("/api/public/subscriptions/confirm/preview", {"token": confirm})
        await subs.confirm(confirm)
        manage = await subs.manage_token(ADDRESS)
        tokens.append(manage)
        assert (await api.client.get(f"/ics/p/{ics[1]}.ics")).status_code == 200
        await api.client.get(f"/ics/p/{ics[1]}.ics")
        await subs.me(manage)
        await subs.me(manage, "PUT", json={"interests": ["kultur"]})
        await subs.post("/api/public/subscriptions/manage-link", {"email": "other@example.org"})
    published = [
        await api.client.get(path)
        for path in (
            "/api/public/feed/events",
            "/ics/all.ics",
            "/ics/k/party.ics",
            "/ics/k/kino.ics",
            "/sitemap.xml",
            "/robots.txt",
            "/api/public/categories",
            "/api/public/getstarted/questions",
            "/api/public/today",
        )
    ]
    for response in published:
        body = response.content.decode("utf-8", "replace") + str(dict(response.headers))
        assert ADDRESS not in body.lower(), response.request.url
        assert not any(t in body for t in tokens), response.request.url
    ours = "\n".join(
        r.getMessage() for r in caplog.records if not r.name.startswith(("httpx", "httpcore"))
    )
    audit = str(await subs.sql("SELECT actor, action, target_id, data FROM audit_entry"))
    cache = await everything_in(redis)
    for name, haystack in (("log", ours), ("audit", audit), ("redis", cache)):
        assert ADDRESS not in haystack.lower(), name
        assert not any(t in haystack for t in tokens), name
    row = (
        str(await subs.sql("SELECT * FROM subscriber"))
        + str(await subs.sql("SELECT * FROM subscription_profile"))
        + str(await subs.sql("SELECT * FROM outbox"))
    )
    assert ADDRESS not in row.lower() and not any(t in row for t in tokens)
    mail_bodies = " ".join(m.text for m in subs.queue.sent)
    assert ADDRESS not in mail_bodies and confirm in mail_bodies
