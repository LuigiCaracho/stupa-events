"""The arq jobs with injected dependencies: outbox, reconcile, digest, purge and the status counters."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest

from app.modules.subscriptions import digest as digest_module
from app.modules.subscriptions.outbox_status import last_reconcile, outbox_status
from tests._support.factories import make_settings
from tests.integration.subscriptions.listmonk_support import (
    KEY,
    NOW,
    add_subscriber,
    enqueue,
    scalar,
)
from worker.digest import build_digest_drafts
from worker.outbox import outbox_run
from worker.privacy import purge_expired
from worker.reconcile import reconcile_listmonk

pytest_plugins = ["tests.integration.subscriptions.listmonk_support"]
pytestmark = pytest.mark.integration


class MemoryRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    async def exists(self, key: str) -> int:
        return int(key in self.data)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        self.data[key] = value

    async def get(self, key: str) -> str | None:
        return self.data.get(key)


def context(maker, fake, redis: MemoryRedis) -> dict[str, Any]:  # noqa: ANN001
    return {
        "settings": make_settings(pgcrypto_email_key=KEY),
        "subs_sessionmaker": maker,
        "app_sessionmaker": maker,
        "listmonk": fake,
        "redis": redis,
    }


async def test_outbox_job_runs_due_jobs(maker, fake) -> None:  # noqa: ANN001
    await enqueue(maker, "upsert", await add_subscriber(maker, "a@example.test"), next_at=NOW)
    ctx = context(maker, fake, MemoryRedis())
    assert (await outbox_run(ctx)).startswith("outbox_run: done=1 failed=0")
    assert fake.by_email("a@example.test") is not None


async def test_reconcile_job_leaves_counters_for_the_status_page(maker, fake) -> None:  # noqa: ANN001
    redis = MemoryRedis()
    line = await reconcile_listmonk(context(maker, fake, redis))
    assert line.startswith("reconcile_listmonk: seen=0")
    stored = await last_reconcile(redis)
    assert stored is not None and stored["seen"] == 0 and "at" in stored
    assert json.loads(redis.data["listmonk:reconcile"])["foreign_on_lists"] == 0


async def test_digest_job_with_nothing_to_send(maker, fake, monkeypatch) -> None:  # noqa: ANN001
    async def none(maker, week_start):  # noqa: ANN001, ANN202
        return []

    monkeypatch.setattr(digest_module, "week_events", none)
    line = await build_digest_drafts(context(maker, fake, MemoryRedis()))
    assert line == "build_digest_drafts: drafts=0 skipped=0"


async def test_purge_job_reports_counts(maker, fake) -> None:  # noqa: ANN001
    line = await purge_expired(context(maker, fake, MemoryRedis()))
    assert line == "purge_expired: pending=0 unsubscribed=0 profiles=0 outbox=0"


async def test_status_counts_backlog_age_and_dead_deletes(maker) -> None:  # noqa: ANN001
    empty = await outbox_status(maker, NOW)
    assert (empty.outbox_pending, empty.outbox_lag_seconds) == (0, 0)
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    delete = await enqueue(maker, "delete", sid)
    from sqlalchemy import text

    async with maker.begin() as session:
        await session.execute(
            text("UPDATE outbox SET created_at = :t"), {"t": NOW - timedelta(hours=2)}
        )
        await session.execute(text("UPDATE outbox SET state = 'dead' WHERE id = :i"), {"i": delete})
    status = await outbox_status(maker, NOW)
    assert (status.outbox_pending, status.outbox_dead, status.outbox_dead_deletes) == (1, 1, 1)
    assert status.outbox_lag_seconds == 7200
    assert await scalar(maker, "SELECT count(*) FROM outbox") == 2
