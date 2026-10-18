"""Idempotent loading of the reference rows (organizations and categories).

Migration `0002_events_core` inserts the same rows on a fresh database. This function
adds what is missing on a database that already exists, and never changes a row.
"""

from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs.models import Organization
from app.modules.taxonomy.models import Category
from app.modules.taxonomy.reference import CATEGORIES, ORGANIZATIONS


async def ensure_reference(session: AsyncSession) -> None:
    """Insert the missing categories (parents first), then the missing organizations."""
    for row in sorted(CATEGORIES, key=lambda r: r["parent_id"] is not None):
        await session.execute(insert(Category).values(**row).on_conflict_do_nothing())
    for row in ORGANIZATIONS:
        await session.execute(insert(Organization).values(**row).on_conflict_do_nothing())
