"""A scratch database for the B1 load check: container, migrations, roles, events, app.

The context manager yields an HTTP client on the real app (public role, no response cache, no
rate limit), the slugs of a sample of events and a function that returns the query plan of a
text search. Everything is thrown away on exit.
"""

from __future__ import annotations

import asyncio
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import create_app
from app.modules.publicapi.db import get_public_session
from app.settings import get_settings
from scripts.b1_load import explain_statement, seed_events
from tests._support.factories import make_settings
from tests.integration.conftest import make_alembic_config

ROLES_SQL = Path(__file__).resolve().parents[2] / "deploy" / "db" / "roles.sql"


def grant_roles(sync_url: str) -> None:
    """Create the roles of `deploy/db/roles.sql` in the scratch database with the password `pw`."""
    engine = create_engine(sync_url)
    with engine.begin() as conn:
        name = conn.execute(text("SELECT current_database()")).scalar_one()
        script = ROLES_SQL.read_text().replace("DATABASE events", f"DATABASE {name}")
        script = re.sub(r"ALTER ROLE events_public SET [^;]+;", "", script)
        conn.exec_driver_sql(script.replace("%", "%%"))
        for role in ("events_app", "events_public"):
            conn.execute(text(f"ALTER ROLE {role} PASSWORD 'pw'"))
        conn.exec_driver_sql(script.replace("%", "%%"))
    engine.dispose()


@asynccontextmanager
async def scratch_app(
    events: int,
) -> AsyncIterator[tuple[AsyncClient, list[str], Callable[[str], Awaitable[Any]]]]:
    """Start the scratch stack; yield `(client, slugs, explain)`."""
    from testcontainers.postgres import PostgresContainer

    os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as container:
        sync_url = container.get_connection_url()
        async_url = sync_url.replace("postgresql+psycopg://", "postgresql+asyncpg://")
        await asyncio.to_thread(command.upgrade, make_alembic_config(async_url), "head")
        await asyncio.to_thread(grant_roles, sync_url)
        engine = create_engine(sync_url)
        slugs = await asyncio.to_thread(seed_events, engine, events)
        engine.dispose()
        public = create_async_engine(
            async_url.replace("test:test", "events_public:pw"), pool_size=4, max_overflow=2
        )
        maker = async_sessionmaker(public, expire_on_commit=False, autoflush=False)

        async def session() -> AsyncIterator[Any]:
            async with maker() as one:
                yield one

        app = create_app(make_settings())
        app.state.arq_pool = None
        app.dependency_overrides[get_public_session] = session
        settings = make_settings()
        app.dependency_overrides[get_settings] = lambda: settings

        async def explain(query: str) -> Any:
            async with maker() as one:
                return (await one.execute(explain_statement(query))).scalar_one()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            try:
                yield client, slugs, explain
            finally:
                await public.dispose()
