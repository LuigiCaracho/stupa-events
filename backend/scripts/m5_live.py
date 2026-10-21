"""Small dossier helpers of the M5 acceptance: a live dossier without poster, and anonymous reads.

`live` creates a dossier of the FSI, lets the editor grant the image exception and fires
T01, T02, T04 (with the location confirmation) and T05. `anonymous` is a client without
session for the public routes; `bump_feed` marks the public snapshots stale after SQL.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import httpx
from arq import create_pool
from arq.connections import RedisSettings

from app.modules.pipeline.actions import FEED_VERSION_KEY, REBUILD_JOB, REBUILD_JOB_ID
from app.settings import get_settings
from scripts import m4_acceptance as m4
from scripts.acceptance_common import API, expect


def anonymous() -> httpx.Client:
    """Return a client without cookies against the API."""
    return httpx.Client(base_url=API, timeout=30.0)


def live(
    organizer: httpx.Client,
    editor: httpx.Client,
    title: str,
    *,
    days: int = 30,
    times: tuple[datetime, datetime] | None = None,
    category: str = "kino",
    fmt: str | None = None,
) -> str:
    """Create and publish a dossier of the FSI (optionally of a format); return its id."""
    eid = m4.create(organizer, title, category=category, days=days)
    if fmt is not None:
        expect(
            organizer.put(
                f"/api/events/{eid}/format", json={"slug": fmt}, headers=m4.etag(organizer, eid)
            ),
            200,
            f"{title}: format {fmt}",
        )
    if times is not None:
        expect(
            organizer.patch(
                f"/api/events/{eid}",
                json={"startsAt": times[0].isoformat(), "endsAt": times[1].isoformat()},
                headers=m4.etag(organizer, eid),
            ),
            200,
            f"{title}: {times[0].isoformat()}",
        )
    expect(
        editor.post(
            f"/api/events/{eid}/actions/image-exception",
            json={"reason": "Abnahme ohne Motiv"},
            headers=m4.etag(editor, eid),
        ),
        200,
        f"{title}: image exception",
    )
    m4.fire(organizer, eid, "T02")
    m4.fire(editor, eid, "T04")
    m4.fire(editor, eid, "T05")
    return eid


def bump_feed() -> None:
    """After a change by SQL: mark the snapshots stale (the view answers) and queue a rebuild.

    `rebuild_public_cache` keeps no result (`keep_result=0`), so nothing waits for it here.
    """

    async def run() -> None:
        pool = await create_pool(
            RedisSettings.from_dsn(get_settings().redis_url),
            default_queue_name=get_settings().arq_queue_name,
        )
        try:
            await pool.incr(FEED_VERSION_KEY)
            await pool.enqueue_job(REBUILD_JOB, _job_id=REBUILD_JOB_ID)
        finally:
            await pool.aclose()

    asyncio.run(run())
