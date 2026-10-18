"""Actions after the commit: idempotent, logged on failure, never rolled back.

Each action runs under the key `event:<id>:rev:<n>:<action>`. The runner claims the key
in Redis with SET NX, so a second run of the same revision does nothing. Without a pool
(development without Redis) the actions are skipped and logged.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.modules.pipeline.transitions import ACTION_ENSURE_DERIVATIVES, ACTION_FEED_INVALIDATE

logger = logging.getLogger("app.pipeline")

FEED_VERSION_KEY = "events:feed:version"
KEY_TTL_SECONDS = 24 * 3600
DERIVE_TASK = "derive_poster"


@dataclass(frozen=True, slots=True)
class Committed:
    """What the follow-up actions need to know about a committed change."""

    event_id: UUID
    rev: int
    poster_id: UUID | None
    poster_has_derivatives: bool


type Action = Callable[[Any, Committed], Awaitable[None]]


async def invalidate_feed_cache(pool: Any, committed: Committed) -> None:
    """Bump the feed version, so a cached feed knows it is stale."""
    await pool.incr(FEED_VERSION_KEY)


async def ensure_derivatives(pool: Any, committed: Committed) -> None:
    """Queue the derive job when the poster still has no public derivatives."""
    if committed.poster_id is None or committed.poster_has_derivatives:
        return
    await pool.enqueue_job(
        DERIVE_TASK, str(committed.poster_id), _job_id=f"derive:{committed.poster_id}"
    )


ACTIONS: dict[str, Action] = {
    ACTION_FEED_INVALIDATE: invalidate_feed_cache,
    ACTION_ENSURE_DERIVATIVES: ensure_derivatives,
}


def action_key(committed: Committed, name: str) -> str:
    """Return the idempotency key `event:<id>:rev:<n>:<action>`."""
    return f"event:{committed.event_id}:rev:{committed.rev}:{name}"


async def run_actions(pool: Any | None, names: tuple[str, ...], committed: Committed) -> None:
    """Run the named actions once each. A failure is logged and swallowed."""
    if pool is None:
        logger.info("post-commit actions skipped, no redis pool (event=%s)", committed.event_id)
        return
    for name in names:
        try:
            claimed = await pool.set(action_key(committed, name), "1", nx=True, ex=KEY_TTL_SECONDS)
            if claimed:
                await ACTIONS[name](pool, committed)
        except Exception:  # noqa: BLE001 - an action never rolls back the commit
            logger.exception("post-commit action %s failed (event=%s)", name, committed.event_id)
