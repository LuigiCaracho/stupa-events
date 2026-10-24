"""The third database connection: role `events_subs`, the only writer of the subscription tables.

It has its own URL (`SUBS_DATABASE_URL`) and no fallback to the application URL. The role has
no `DELETE`; personal data leaves only through the `privacy_*` functions. Pool 3 plus 1 stays
under the role's connection limit of 6, shared by API and worker.
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
def get_subs_engine() -> AsyncEngine:
    """Create the engine of the subscription role once.

    Raises:
        ServiceUnavailableError: `SUBS_DATABASE_URL` is not set.
    """
    url = get_settings().subs_database_url
    if not url:
        raise ServiceUnavailableError("The subscription database is not configured.")
    return create_async_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=1)


def get_subs_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return a session factory on the subscription connection."""
    return async_sessionmaker(get_subs_engine(), expire_on_commit=False, autoflush=False)


async def get_subs_session() -> AsyncGenerator[AsyncSession]:
    """Yield a session on the subscription connection; roll back what was not committed."""
    async with get_subs_sessionmaker()() as session:
        yield session
