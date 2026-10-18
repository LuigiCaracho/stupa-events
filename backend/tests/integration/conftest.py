"""Integration fixtures: Postgres 16 and Redis from testcontainers, migrated to head.

The tests skip when no Docker runtime is reachable. Every migrated schema is shared by
the session; `truncate_all` clears the data between tests. A module that adds tables
extends `TRUNCATE_TABLES` through its own conftest fixture, not in this file.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

TRUNCATE_TABLES: list[str] = [
    "audit_verification",
    "markdown_image",
    "auth_session",
    "principal",
]


def make_alembic_config(async_url: str) -> Config:
    """Build an Alembic config that points at `async_url`."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "migrations")
    cfg.set_main_option("sqlalchemy.url", async_url)
    return cfg


@pytest.fixture(scope="session")
def pg_urls() -> Iterator[tuple[str, str]]:
    """Start a Postgres 16 container; yield the sync and the async URL."""
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed")
    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    try:
        container = PostgresContainer("postgres:16-alpine", driver="psycopg")
        container.start()
    except Exception as exc:  # pragma: no cover - environment without Docker
        pytest.skip(f"no Docker runtime: {exc}")
    sync_url = container.get_connection_url()
    try:
        yield sync_url, sync_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
    finally:
        container.stop()


@pytest.fixture(scope="session")
def migrated(pg_urls: tuple[str, str]) -> tuple[str, str]:
    """Migrate the schema to head once; return the sync and the async URL."""
    command.upgrade(make_alembic_config(pg_urls[1]), "head")
    return pg_urls


@pytest.fixture
def alembic_cfg(migrated: tuple[str, str]) -> Config:
    """The Alembic config of the migrated database."""
    return make_alembic_config(migrated[1])


@pytest.fixture
def engine(migrated: tuple[str, str]) -> Iterator[Engine]:
    """A sync engine for assertions; the data is cleared before and after the test."""
    eng = create_engine(migrated[0])
    _truncate(eng)
    try:
        yield eng
    finally:
        _truncate(eng)
        eng.dispose()


def _truncate(eng: Engine) -> None:
    with eng.begin() as conn:
        existing = set(
            conn.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).scalars()
        )
        tables = [t for t in TRUNCATE_TABLES if t in existing]
        if tables:
            conn.execute(text(f"TRUNCATE {', '.join(tables)} RESTART IDENTITY CASCADE"))
        if "audit_entry" in existing:
            # The append-only trigger blocks TRUNCATE for everybody; a test database
            # resets the chain with the triggers off, as the superuser.
            conn.execute(text("ALTER TABLE audit_entry DISABLE TRIGGER USER"))
            conn.execute(text("TRUNCATE audit_entry RESTART IDENTITY"))
            conn.execute(text("ALTER TABLE audit_entry ENABLE TRIGGER USER"))


@pytest_asyncio.fixture
async def session(migrated: tuple[str, str], engine: Engine) -> AsyncIterator[AsyncSession]:
    """An async session on the migrated database (the test commits itself)."""
    async_engine = create_async_engine(migrated[1])
    async with async_sessionmaker(async_engine, expire_on_commit=False)() as db:
        yield db
    await async_engine.dispose()


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    """Start a Redis container and yield its URL."""
    try:
        from testcontainers.redis import RedisContainer
    except ImportError:  # pragma: no cover
        pytest.skip("testcontainers not installed")
    try:
        container = RedisContainer("redis:7-alpine")
        container.start()
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"no Docker runtime: {exc}")
    try:
        yield f"redis://{container.get_container_host_ip()}:{container.get_exposed_port(6379)}/0"
    finally:
        container.stop()
