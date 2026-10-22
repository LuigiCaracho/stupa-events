"""Idempotent loading of the reference rows (organizations, categories, venues).

Migrations `0002_events_core` and `0003_roles_taxonomy` insert the same rows on a fresh
database. This function adds what is missing on a database that already exists. It never
overwrites a row, except for the fixed renames and fixes of `reference_m2`, which only
repeat what `0003` did.
"""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.orgs.models import Organization
from app.modules.taxonomy.models import Category, Venue
from app.modules.taxonomy.reference import CATEGORIES, ORGANIZATIONS
from app.modules.taxonomy.reference_descriptions import DESCRIPTIONS
from app.modules.taxonomy.reference_m2 import category_renames, organization_legacy_fixes
from app.modules.taxonomy.venue_reference import VENUES


async def ensure_reference(session: AsyncSession) -> None:
    """Insert the missing categories (parents first), organizations and venues."""
    for row in sorted(CATEGORIES, key=lambda r: r["parent_id"] is not None):
        await session.execute(insert(Category).values(**row).on_conflict_do_nothing())
    for slug, text in DESCRIPTIONS.items():
        await session.execute(
            update(Category)
            .where(Category.slug == slug, Category.description.is_(None))
            .values(description=text)
        )
    for row in ORGANIZATIONS:
        await session.execute(insert(Organization).values(**row).on_conflict_do_nothing())
    for category_id, slug in category_renames():
        await session.execute(update(Category).where(Category.id == category_id).values(slug=slug))
    for org_id, ids in organization_legacy_fixes():
        await session.execute(
            update(Organization).where(Organization.id == org_id).values(legacy_wp_ids=ids)
        )
    for row in VENUES:
        await session.execute(insert(Venue).values(**row).on_conflict_do_nothing())
