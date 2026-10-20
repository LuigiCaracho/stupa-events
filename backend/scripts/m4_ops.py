"""Operations of the M4 acceptance outside the API: worker jobs, SQL, Redis, process memory.

Jobs run once on the queue of the running worker (`stupa-worker`), the way `m3_worker`
runs `advance_states`. SQL only reads, or moves clocks (`created_at`, `gc_marked_at`) for
the garbage collector. Redis is the dev compose container; stopping it is the point of
check (j), and `redis_up` brings it back and restarts the worker, which exits without it.
"""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job
from sqlalchemy import create_engine, text

from app.settings import get_settings

REDIS_CONTAINER = "stupa-events-dev-redis-1"
JOB_TIMEOUT_SECONDS = 120


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(get_settings().redis_url)


def run_job(name: str, *args: object) -> str:
    """Enqueue `name` on the running worker and return its result as text."""

    async def run() -> str:
        pool = await create_pool(
            _redis_settings(), default_queue_name=get_settings().arq_queue_name
        )
        try:
            job = await pool.enqueue_job(name, *args)
            assert job is not None
            return str(await job.result(timeout=JOB_TIMEOUT_SECONDS))
        finally:
            await pool.aclose()

    return asyncio.run(run())


def job_result(job_id: str, timeout: float = 60) -> str:
    """Wait for the result of the job `job_id` (a mail job: the idempotency key)."""

    async def run() -> str:
        pool = await create_pool(
            _redis_settings(), default_queue_name=get_settings().arq_queue_name
        )
        try:
            job = Job(job_id, pool, _queue_name=get_settings().arq_queue_name)
            return str(await job.result(timeout=timeout))
        finally:
            await pool.aclose()

    return asyncio.run(run())


def redis_delete(key: str) -> None:
    """Delete one Redis key (the daily claim of `gc_media`)."""
    subprocess.run(
        ["docker", "exec", REDIS_CONTAINER, "redis-cli", "DEL", key],
        check=True,
        capture_output=True,
    )


def reset_upload_limits() -> None:
    """Drop the hourly upload counters, so repeated runs stay under `rl_attachments_per_hour`."""
    keys = subprocess.run(
        ["docker", "exec", REDIS_CONTAINER, "redis-cli", "--scan", "--pattern", "rl:attachments:*"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.split()
    for key in keys:
        redis_delete(key)


def query(statement: str, **params: object) -> list[tuple[Any, ...]]:
    """Run one statement on the dev database as the app user and return the rows."""
    engine = create_engine(get_settings().database_url.replace("+asyncpg", "+psycopg"))
    try:
        with engine.begin() as conn:
            result = conn.execute(text(statement), params)
            return [tuple(row) for row in result] if result.returns_rows else []
    finally:
        engine.dispose()


def redis_down() -> None:
    """Stop the Redis container."""
    subprocess.run(["docker", "stop", REDIS_CONTAINER], check=True, capture_output=True)


def redis_up() -> None:
    """Start Redis again and restart the worker, which exits once Redis is gone."""
    subprocess.run(["docker", "start", REDIS_CONTAINER], check=True, capture_output=True)
    subprocess.run(
        ["docker", "exec", REDIS_CONTAINER, "sh", "-c", "until redis-cli ping; do sleep 1; done"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["systemctl", "--user", "restart", "stupa-worker"], check=True)


def unit_log(unit: str, since: str) -> str:
    """Return the journal of a user unit since `since` (journalctl time syntax)."""
    out = subprocess.run(
        ["journalctl", "--user", "-u", unit, "--since", since, "--no-pager", "-o", "cat"],
        check=True,
        capture_output=True,
        text=True,
    )
    return out.stdout


def unit_memory_kib(unit: str) -> dict[str, int]:
    """Return `VmRSS` and `VmHWM` (peak) of the main process of a user unit in KiB."""
    pid = subprocess.run(
        ["systemctl", "--user", "show", "-p", "MainPID", "--value", unit],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = Path(f"/proc/{pid}/status").read_text().splitlines()
    fields = dict(line.split(":", 1) for line in status if line.startswith(("VmRSS", "VmHWM")))
    return {name: int(value.split()[0]) for name, value in fields.items()}
