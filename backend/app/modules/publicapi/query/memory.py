"""The text search path: one scan of the view, then rank, filter, page and count in memory.

The match (full text or trigram) is the expensive part, so it runs once per request. It returns
the hits of the time window with the card columns and the rank (at most `HIT_CAP`, best first);
the category and organization filters, the total, the page and every disjunctive facet are then
computed from those rows in Python. A search with more than `HIT_CAP` hits counts only the best
`HIT_CAP` in its total and facets. Unlike the SQL facets, a chosen organization with no hit does
not stay in the list (the public role cannot read organization names outside events).
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from typing import Any

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi.clock import BERLIN
from app.modules.publicapi.query import cards, facets
from app.modules.publicapi.query.columns import CARD
from app.modules.publicapi.query.filters import SiteFilters, terms, where
from app.modules.publicapi.query.search import MAX_OFFSET, Position, encode_offset, rank_sql
from app.modules.publicapi.site_schemas import (
    PublicFacetCategory,
    PublicFacetMonth,
    PublicFacetOrganization,
    PublicFacets,
    PublicSearchOut,
)
from app.modules.search.params import Params

HIT_CAP = 2000
FACET_LIMITS = (30, 30, 12)


def hits_sql(filters: SiteFilters) -> tuple[str, Params]:
    """Build the one scan: the words and the time window, best rank first, with its parameters."""
    params = Params()
    words = terms(filters, params)
    condition = where(filters, params, words, skip=frozenset({"category", "organization", "month"}))
    sql = (
        f"SELECT {CARD}, {rank_sql(words)} AS rank FROM public_event_v WHERE {condition}"
        f" ORDER BY rank DESC, starts_at, id LIMIT {HIT_CAP}"
    )
    return sql, params


async def hits(session: AsyncSession, filters: SiteFilters) -> list[Row[Any]]:
    """Scan the view once: the rows that match the words in the time window, best first."""
    sql, params = hits_sql(filters)
    return list((await session.execute(params.statement(sql))).all())


def _in_range(row: Row[Any], filters: SiteFilters) -> bool:
    return (filters.start is None or row.ends_at >= filters.start) and (
        filters.end is None or row.starts_at < filters.end
    )


def _in_categories(row: Row[Any], filters: SiteFilters) -> bool:
    chosen = filters.categories
    return not chosen or row.category_slug in chosen or row.category_parent_slug in chosen


def _in_organizations(row: Row[Any], filters: SiteFilters) -> bool:
    return not filters.organizations or row.organization_slug in filters.organizations


def select(
    rows: Iterable[Row[Any]], filters: SiteFilters, *, skip: frozenset[str] = frozenset()
) -> list[Row[Any]]:
    """Apply the filters of the request except those named in `skip`."""
    checks: list[Callable[[Row[Any], SiteFilters], bool]] = []
    if "month" not in skip:
        checks.append(_in_range)
    if "category" not in skip:
        checks.append(_in_categories)
    if "organization" not in skip:
        checks.append(_in_organizations)
    return [row for row in rows if all(check(row, filters) for check in checks)]


def _top(counter: Counter[Any], limit: int, name: Callable[[Any], str]) -> list[Any]:
    return sorted(counter.items(), key=lambda item: (-item[1], name(item[0])))[:limit]


def _category_facets(rows: list[Row[Any]], filters: SiteFilters) -> list[PublicFacetCategory]:
    counts: Counter[tuple[str, str]] = Counter()
    for row in select(rows, filters, skip=frozenset({"category"})):
        if row.category_slug:
            counts[(row.category_slug, row.category_name)] += 1
        if row.category_parent_slug:
            counts[(row.category_parent_slug, row.category_parent_name)] += 1
    top = _top(counts, FACET_LIMITS[0], lambda key: key[1])
    return [PublicFacetCategory(slug=s, name=n, count=c) for (s, n), c in top]


def _organization_facets(
    rows: list[Row[Any]], filters: SiteFilters
) -> list[PublicFacetOrganization]:
    counts: Counter[tuple[str, str, str]] = Counter()
    for row in select(rows, filters, skip=frozenset({"organization"})):
        counts[(row.organization_slug, row.organization_name, row.organization_short)] += 1
    top = _top(counts, FACET_LIMITS[1], lambda key: key[1])
    return [PublicFacetOrganization(slug=s, name=n, short=h, count=c) for (s, n, h), c in top]


def _month_facets(rows: list[Row[Any]], filters: SiteFilters) -> list[PublicFacetMonth]:
    counts = Counter(
        row.starts_at.astimezone(BERLIN).strftime("%Y-%m")
        for row in select(rows, filters, skip=frozenset({"month"}))
    )
    ordered = sorted(counts.items(), reverse=filters.descending)[: FACET_LIMITS[2]]
    return [PublicFacetMonth(month=m, count=c) for m, c in ordered]


async def search(
    session: AsyncSession, filters: SiteFilters, position: Position, limit: int, *, first: bool
) -> PublicSearchOut:
    """Answer a text search; total and facets only for the first page."""
    found = await hits(session, filters)
    chosen = select(found, filters)
    shown = chosen[position.offset : position.offset + limit]
    following = position.offset + limit
    more = following < len(chosen) and following <= MAX_OFFSET
    return PublicSearchOut(
        items=[cards.to_card(row) for row in shown],
        next_cursor=encode_offset(following) if more else None,
        total=len(chosen) if first else None,
        facets=await _facets(session, found, filters) if first else None,
    )


async def _facets(
    session: AsyncSession, found: list[Row[Any]], filters: SiteFilters
) -> PublicFacets:
    categories = await facets.with_selected(
        session, _category_facets(found, filters), filters.categories
    )
    return PublicFacets(
        categories=categories,
        organizations=_organization_facets(found, filters),
        months=_month_facets(found, filters),
    )
