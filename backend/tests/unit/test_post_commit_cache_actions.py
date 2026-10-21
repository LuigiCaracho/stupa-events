"""The feed invalidation: bump the counter, queue one rebuild, never fail the commit."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.events.postcommit import (
    FEED_VERSION_KEY,
    REBUILD_JOB,
    REBUILD_JOB_ID,
    invalidate_feed_cache,
    invalidate_public,
    request_rebuild,
)


class Pool:
    def __init__(self, *, fail_enqueue: bool = False, fail_incr: bool = False) -> None:
        self.counter = 0
        self.jobs: list[tuple[str, dict[str, Any]]] = []
        self.fail_enqueue, self.fail_incr = fail_enqueue, fail_incr

    async def incr(self, key: str) -> int:
        if self.fail_incr:
            raise ConnectionError("down")
        assert key == FEED_VERSION_KEY
        self.counter += 1
        return self.counter

    async def enqueue_job(self, name: str, **kwargs: Any) -> None:
        if self.fail_enqueue:
            raise ConnectionError("down")
        self.jobs.append((name, kwargs))


async def test_invalidation_bumps_the_version_and_queues_one_debounced_job() -> None:
    pool = Pool()
    await invalidate_feed_cache(pool, None)
    assert pool.counter == 1 and pool.jobs == [(REBUILD_JOB, {"_job_id": REBUILD_JOB_ID})]


async def test_a_failing_queue_is_logged_and_swallowed(caplog: pytest.LogCaptureFixture) -> None:
    await request_rebuild(Pool(fail_enqueue=True))
    assert "could not queue" in caplog.text


async def test_invalidate_public_tolerates_no_pool_and_a_broken_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    await invalidate_public(None)
    working = Pool()
    await invalidate_public(working)
    assert working.counter == 1
    await invalidate_public(Pool(fail_incr=True))
    assert "feed invalidation failed" in caplog.text
