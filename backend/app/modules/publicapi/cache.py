"""Snapshots of the public feed and calendars in Redis (contract 9.5).

The worker builds the full feed and every ICS and writes them as Redis hashes
`events:public:snap:<name>` with the fields `version`, `etag`, `body`, `contentType` and
`generatedAt`. The API serves a snapshot only when its version equals the counter
`events:feed:version` and it is not older than the allowed age; otherwise (or on any Redis
error) it builds live from the view. A snapshot is never a source of truth, only a copy.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from app.modules.pipeline.actions import FEED_VERSION_KEY

logger = logging.getLogger("app.public")

SNAPSHOT_PREFIX = "events:public:snap:"
SNAPSHOT_TTL_SECONDS = 2 * 3600
FEED = "feed"
ICS_ALL = "ics:all"


def ics_name(slug: str) -> str:
    """Return the snapshot name of the calendar of one category."""
    return f"ics:k:{slug}"


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One stored body with the version it was built from."""

    version: int
    etag: str
    body: bytes
    content_type: str
    generated_at: datetime


def etag_of(body: bytes) -> str:
    """Return the strong ETag of a body: a hash of its bytes."""
    return f'"{hashlib.sha256(body).hexdigest()[:32]}"'


def _decode(raw: dict[Any, Any]) -> dict[str, Any]:
    decoded: dict[str, Any] = {}
    for key, value in raw.items():
        name = key.decode() if isinstance(key, bytes) else key
        keep = name == "body" or not isinstance(value, bytes)
        decoded[name] = value if keep else value.decode()
    return decoded


async def current_version(redis: Any) -> int:
    """Read the feed version counter (0 when nothing was ever published)."""
    return int(await redis.get(FEED_VERSION_KEY) or 0)


async def load(
    redis: Any, name: str, *, max_age_seconds: int, now: datetime | None = None
) -> Snapshot | None:
    """Return the snapshot `name` when it is fresh, else `None`; Redis errors give `None`.

    Fresh means: the version equals the counter and the snapshot is not older than
    `max_age_seconds`.
    """
    if redis is None:
        return None
    try:
        version = await current_version(redis)
        raw = _decode(await redis.hgetall(f"{SNAPSHOT_PREFIX}{name}"))
        if not raw or int(raw["version"]) != version:
            return None
        built = datetime.fromisoformat(raw["generatedAt"])
        if (now or datetime.now(UTC)) - built > timedelta(seconds=max_age_seconds):
            return None
        return Snapshot(version, raw["etag"], raw["body"], raw["contentType"], built)
    except Exception:  # noqa: BLE001 - a broken cache is a miss, never a 500
        logger.warning("public snapshot unavailable (name=%s)", name, exc_info=True)
        return None


async def store(redis: Any, snapshots: dict[str, Snapshot]) -> None:
    """Write all snapshots in one transaction (`MULTI`), each with a two hour lifetime."""
    async with redis.pipeline(transaction=True) as pipe:
        for name, snap in snapshots.items():
            key = f"{SNAPSHOT_PREFIX}{name}"
            pipe.delete(key)
            pipe.hset(
                key,
                mapping={
                    "version": snap.version,
                    "etag": snap.etag,
                    "body": snap.body,
                    "contentType": snap.content_type,
                    "generatedAt": snap.generated_at.isoformat(),
                },
            )
            pipe.expire(key, SNAPSHOT_TTL_SECONDS)
        await pipe.execute()
