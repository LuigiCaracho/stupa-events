"""Worker part of the M3 acceptance: one manual `advance_states` run on the real worker.

The quarter-hourly cron of `advance_states` is also a plain arq function, so the script
enqueues it once on the queue of the running worker (`stupa-worker`) and reads the log
line it returns. Time is moved by direct SQL on the dates only (`publish_at`, `starts_at`,
`ends_at`); state changes stay with the worker and its guards. The blocked case (a poster
that turned unusable) needs a disabled trigger and stays with `test_advance_states.py`.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from arq import create_pool
from arq.connections import RedisSettings
from sqlalchemy import create_engine, text

from app.settings import get_settings
from scripts.acceptance_common import step

RUN_TIMEOUT_SECONDS = 120


def run_advance_once() -> str:
    """Enqueue `advance_states` on the running worker and return its summary line."""
    settings = get_settings()

    async def run() -> str:
        pool = await create_pool(
            RedisSettings.from_dsn(settings.redis_url), default_queue_name=settings.arq_queue_name
        )
        try:
            job = await pool.enqueue_job("advance_states")
            assert job is not None
            return str(await job.result(timeout=RUN_TIMEOUT_SECONDS))
        finally:
            await pool.aclose()

    line = asyncio.run(run())
    step(f"worker advance_states: {line}")
    return line


def execute(statement: str, **params: object) -> None:
    """Run one statement on the dev database as the app user."""
    engine = create_engine(get_settings().database_url.replace("+asyncpg", "+psycopg"))
    try:
        with engine.begin() as conn:
            conn.execute(text(statement), params)
    finally:
        engine.dispose()


def shift_dates(eid: str, **columns: datetime) -> None:
    """Set date columns of one dossier by direct SQL (the clock moves, not the state)."""
    assignments = ", ".join(f"{name} = :{name}" for name in columns)
    execute(f"UPDATE event SET {assignments} WHERE id = :i", i=eid, **columns)


def now() -> datetime:
    """Return the current UTC time."""
    return datetime.now(UTC)


def ended(hours: int = 13) -> dict[str, datetime]:
    """Return `starts_at` and `ends_at` of an event that ended `hours` ago."""
    end = now() - timedelta(hours=hours)
    return {"starts_at": end - timedelta(hours=3), "ends_at": end}
