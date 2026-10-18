"""Organization scope: bind the slugs of a principal to ids and list scoped ids.

The principal carries organization roles as slugs only. `bind` maps them to ids with one
query per request, so `Principal.has(perm, org_id)` can decide. `org_ids_for` and
`readable_org_ids` return `None` for a global right and else the set of organization ids
a list must be filtered to, in SQL (PLAN 5.4).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.orgs.models import Organization

READ_ALL = "event.read_all"


async def bind(session: AsyncSession, principal: Principal) -> None:
    """Bind the organization slugs of the principal to ids (one query, idempotent)."""
    slugs = set(principal.org_roles)
    if not slugs or slugs <= set(principal.org_ids):
        return
    rows = (
        await session.execute(
            select(Organization.slug, Organization.id).where(Organization.slug.in_(slugs))
        )
    ).all()
    principal.bind_org_ids({slug: org_id for slug, org_id in rows})


async def org_refs(session: AsyncSession, principal: Principal) -> dict[str, Organization]:
    """Return the organizations of the principal's roles by slug, in one query.

    The query is the one `bind` runs, widened to whole rows, and it binds the ids too.
    """
    slugs = set(principal.org_roles)
    if not slugs:
        return {}
    rows = (
        (await session.execute(select(Organization).where(Organization.slug.in_(slugs))))
        .scalars()
        .all()
    )
    principal.bind_org_ids({org.slug: org.id for org in rows})
    return {org.slug: org for org in rows}


async def _ids_of(session: AsyncSession, principal: Principal, slugs: set[str]) -> set[UUID]:
    await bind(session, principal)
    return {UUID(principal.org_ids[slug]) for slug in slugs if slug in principal.org_ids}


async def org_ids_for(session: AsyncSession, principal: Principal, perm: str) -> set[UUID] | None:
    """Return the organizations in which `perm` holds.

    Returns:
        `None` when the right is global, else the ids of the organizations whose role
        grants it. Never an empty-means-all value: an empty set matches nothing.
    """
    if principal.has(perm):
        return None
    return await _ids_of(session, principal, principal.org_slugs_with(perm))


async def readable_org_ids(session: AsyncSession, principal: Principal) -> set[UUID] | None:
    """Return the organizations whose events the principal reads (`None` for all)."""
    if principal.has(READ_ALL):
        return None
    return await _ids_of(session, principal, set(principal.org_roles))


def restricted_to_own(principal: Principal, org_id: UUID) -> bool:
    """Tell if the principal may touch only dossiers it created in `org_id`.

    A role without `event.submit` (the submitter) works on its own dossiers only.
    """
    return not principal.has("event.submit", org_id)
