"""The second database connection: role `events_public`, `SELECT` on `public_event_v` only.

Only the public router uses this engine. It has its own URL (`PUBLIC_DATABASE_URL`) and
there is no fallback to the application URL, because the point of the second role is that
a bug in a public route cannot read a table.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.settings import get_settings
from app.shared.errors import ServiceUnavailableError


@lru_cache
def get_public_engine() -> AsyncEngine:
    """Create the engine of the public role once.

    Raises:
        ServiceUnavailableError: `PUBLIC_DATABASE_URL` is not set.
    """
    url = get_settings().public_database_url
    if not url:
        raise ServiceUnavailableError("The public database is not configured.")
    return create_async_engine(url, pool_pre_ping=True, pool_size=4, max_overflow=2)


async def get_public_session() -> AsyncGenerator[AsyncSession]:
    """Yield a read-only session on the public connection."""
    maker = async_sessionmaker(get_public_engine(), expire_on_commit=False, autoflush=False)
    async with maker() as session:
        yield session
