"""The response cache of the public routes: Redis hashes, valid for one feed version.

Key `events:public:resp:<sha256(path + normalized query)>`, value `{version, etag, body,
contentType, generatedAt}`. A stored answer counts only while its version equals the counter
`events:feed:version`, which every publish, archive, cancel, poster change or taxonomy edit
bumps; the TTL of a route covers the answers that also age with time. The version is read
before the answer is built, so a change during the build leaves the stored copy stale. Redis
errors are misses, never a 500; only a 200 is stored. `serve` adds `ETag`, `If-None-Match`
and the cache headers, and counts a miss against the rate limit before it builds.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response

from app.modules.publicapi import cache
from app.modules.publicapi.etag import matches

logger = logging.getLogger("app.public")

RESPONSE_PREFIX = "events:public:resp:"
SWR = "public, max-age=60, stale-while-revalidate=30"
LONG = "public, max-age=300"


@dataclass(frozen=True, slots=True)
class Built:
    """A built answer: its bytes and media type."""

    body: bytes
    content_type: str
    status: int = 200


def cache_key(path: str, params: Mapping[str, Any]) -> str:
    """Return the Redis key of a path with its normalized parameters."""
    raw = path + "?" + json.dumps(params, sort_keys=True, default=str, separators=(",", ":"))
    return RESPONSE_PREFIX + hashlib.sha256(raw.encode()).hexdigest()


async def _load(redis: Any, key: str, version: int) -> tuple[str, Built] | None:
    try:
        raw = await redis.hgetall(key)
        data = {(k.decode() if isinstance(k, bytes) else k): v for k, v in raw.items()}
        if not data or int(data["version"]) != version:
            return None
        etag = data["etag"].decode() if isinstance(data["etag"], bytes) else data["etag"]
        kind = data["contentType"]
        return etag, Built(data["body"], kind.decode() if isinstance(kind, bytes) else kind)
    except Exception:  # noqa: BLE001 - a broken cache is a miss
        logger.warning("public response cache unavailable", exc_info=True)
        return None


async def _store(redis: Any, key: str, version: int, etag: str, built: Built, ttl: int) -> None:
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(key)
            pipe.hset(
                key,
                mapping={
                    "version": version,
                    "etag": etag,
                    "body": built.body,
                    "contentType": built.content_type,
                    "generatedAt": datetime.now(UTC).isoformat(),
                },
            )
            pipe.expire(key, ttl)
            await pipe.execute()
    except Exception:  # noqa: BLE001 - a failed write only costs the next request
        logger.warning("public response cache write failed", exc_info=True)


async def _version(redis: Any) -> int | None:
    if redis is None:
        return None
    try:
        return await cache.current_version(redis)
    except Exception:  # noqa: BLE001
        logger.warning("public response cache version unavailable", exc_info=True)
        return None


def _respond(request: Request, etag: str, built: Built, headers: Mapping[str, str]) -> Response:
    sent = {"ETag": etag, **headers}
    if built.status != 200:
        sent["Cache-Control"] = "no-cache"
    elif matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=sent)
    return Response(
        built.body, status_code=built.status, media_type=built.content_type, headers=sent
    )


async def serve(
    request: Request,
    *,
    key: str,
    ttl: int,
    cache_control: str,
    build: Callable[[], Awaitable[Built]],
    on_miss: Callable[[], Awaitable[None]],
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Answer from the cache, or count the miss, build, store and answer.

    Raises:
        RateLimitedError: `on_miss` refused the request.
    """
    redis = getattr(request.app.state, "arq_pool", None)
    version = await _version(redis)
    sent = {"Cache-Control": cache_control, **(headers or {})}
    if version is not None:
        hit = await _load(redis, key, version)
        if hit is not None:
            return _respond(request, hit[0], hit[1], sent)
    await on_miss()
    built = await build()
    etag = cache.etag_of(built.body)
    if version is not None and built.status == 200:
        await _store(redis, key, version, etag, built, ttl)
    return _respond(request, etag, built, sent)
