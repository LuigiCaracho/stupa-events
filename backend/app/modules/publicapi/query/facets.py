"""Total and disjunctive facets of a search (contract 2.2.4).

Every facet counts over all filters except its own, so choosing a chip leaves its siblings
with numbers. A category counts for its main category and its parent. Chosen values with a
count of zero stay in the list. The queries run one after another on one session.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi.query.filters import SiteFilters, where
from app.modules.publicapi.site_schemas import (
    PublicFacetCategory,
    PublicFacetMonth,
    PublicFacetOrganization,
    PublicFacets,
)
from app.modules.search.params import Params

CATEGORY_LIMIT, ORGANIZATION_LIMIT, MONTH_LIMIT = 30, 30, 12
BERLIN_MONTH = "to_char(timezone('Europe/Berlin', starts_at), 'YYYY-MM')"


async def total(session: AsyncSession, filters: SiteFilters) -> int:
    """Count the events that pass every filter."""
    params = Params()
    condition = where(filters, params, [])
    sql = f"SELECT count(*) FROM public_event_v WHERE {condition}"
    return (await session.execute(params.statement(sql))).scalar_one()


async def _categories(session: AsyncSession, filters: SiteFilters) -> list[PublicFacetCategory]:
    params = Params()
    condition = where(filters, params, [], skip=frozenset({"category"}))
    sql = (
        "SELECT slug, name, count(*) AS n FROM ("
        f" SELECT category_slug AS slug, category_name AS name FROM public_event_v"
        f" WHERE {condition} AND category_slug IS NOT NULL"
        " UNION ALL"
        f" SELECT category_parent_slug, category_parent_name FROM public_event_v"
        f" WHERE {condition} AND category_parent_slug IS NOT NULL) s"
        f" GROUP BY slug, name ORDER BY n DESC, name LIMIT {CATEGORY_LIMIT}"
    )
    found = [
        PublicFacetCategory(slug=r.slug, name=r.name, count=r.n)
        for r in (await session.execute(params.statement(sql))).all()
    ]
    return await with_selected(session, found, filters.categories)


async def with_selected(
    session: AsyncSession, found: list[PublicFacetCategory], selected: tuple[str, ...]
) -> list[PublicFacetCategory]:
    """Append the chosen categories that have no hit, with a count of zero."""
    missing = [s for s in selected if s not in {c.slug for c in found}]
    if not missing:
        return found
    names = (
        await session.execute(
            text("SELECT slug, name FROM public_category_v WHERE slug = ANY(:s)").bindparams(
                s=missing
            )
        )
    ).all()
    return found + [PublicFacetCategory(slug=r.slug, name=r.name, count=0) for r in names]


async def _organizations(
    session: AsyncSession, filters: SiteFilters
) -> list[PublicFacetOrganization]:
    params = Params()
    condition = where(filters, params, [], skip=frozenset({"organization"}))
    sql = (
        "SELECT organization_slug AS slug, organization_name AS name,"
        " organization_short AS short, count(*) AS n FROM public_event_v"
        f" WHERE {condition} GROUP BY 1, 2, 3 ORDER BY n DESC, name LIMIT {ORGANIZATION_LIMIT}"
    )
    return [
        PublicFacetOrganization(slug=r.slug, name=r.name, short=r.short, count=r.n)
        for r in (await session.execute(params.statement(sql))).all()
    ]


async def _months(session: AsyncSession, filters: SiteFilters) -> list[PublicFacetMonth]:
    params = Params()
    condition = where(filters, params, [], skip=frozenset({"month"}))
    order = "DESC" if filters.descending else "ASC"
    sql = (
        f"SELECT {BERLIN_MONTH} AS month, count(*) AS n FROM public_event_v"
        f" WHERE {condition} GROUP BY 1 ORDER BY month {order} LIMIT {MONTH_LIMIT}"
    )
    return [
        PublicFacetMonth(month=r.month, count=r.n)
        for r in (await session.execute(params.statement(sql))).all()
    ]


async def facets(session: AsyncSession, filters: SiteFilters) -> PublicFacets:
    """Compute the three facets, one query after the other."""
    return PublicFacets(
        categories=await _categories(session, filters),
        organizations=await _organizations(session, filters),
        months=await _months(session, filters),
    )
