"""Fixtures of the public API tests: the events harness, a recording Redis pool, the worker context."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests._support.factories import make_settings
from tests.integration.events.harness import Api, api, clean_events, db_roles  # noqa: F401


class RealPool(Redis):
    """A Redis client that also records the jobs the API would queue."""

    jobs: list[tuple[str, dict[str, Any]]]

    async def enqueue_job(self, name: str, *args: Any, **kwargs: Any) -> None:
        self.jobs.append((name, kwargs))


@pytest_asyncio.fixture
async def pool(api: Api, redis_url: str) -> AsyncIterator[RealPool]:  # noqa: F811
    client = RealPool.from_url(redis_url)
    client.jobs = []
    await client.flushall()
    api.app.state.arq_pool = client
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture
def ctx(db_roles: tuple[str, str], pool: RealPool) -> dict[str, Any]:  # noqa: F811
    engine = create_async_engine(db_roles[1].replace("postgresql+psycopg", "postgresql+asyncpg"))
    return {
        "redis": pool,
        "settings": make_settings(),
        "public_sessionmaker": async_sessionmaker(engine, expire_on_commit=False),
    }
