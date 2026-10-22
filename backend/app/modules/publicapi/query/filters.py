"""The conditions of the public list: time, category, organization and text, as bound SQL.

`SiteFilters` is the parsed request. `where` renders it for `public_event_v`; a facet passes
its own name in `skip`, so it counts over every filter except itself (disjunctive facets).
All values are bound parameters; the SQL text holds only column names and placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.types import String

from app.modules.search.clauses import WordSql, word_match, word_sql
from app.modules.search.params import Params
from app.modules.search.words import Word

TITLE_FOLDED = "immutable_unaccent(title)"
TSV = "search_tsv"


@dataclass(frozen=True, slots=True)
class SiteFilters:
    """The filters of one request; `start` is inclusive, `end` exclusive."""

    now: datetime
    words: tuple[Word, ...] = ()
    categories: tuple[str, ...] = ()
    organizations: tuple[str, ...] = ()
    start: datetime | None = None
    end: datetime | None = None
    past: bool = False

    @property
    def ranged(self) -> bool:
        """Tell if `from` or `to` were given (then `past` does not apply)."""
        return self.start is not None or self.end is not None

    @property
    def descending(self) -> bool:
        """Past listings run from the newest to the oldest event."""
        return self.past and not self.ranged


def terms(filters: SiteFilters, params: Params) -> list[WordSql]:
    """Bind the search words once; the match and the rank share them."""
    return [word_sql(params, word) for word in filters.words]


def _time(filters: SiteFilters, params: Params, *, with_range: bool) -> list[str]:
    parts: list[str] = []
    if filters.ranged:
        if with_range and filters.start is not None:
            parts.append(f"ends_at >= {params.bind(filters.start, DateTime(timezone=True))}")
        if with_range and filters.end is not None:
            parts.append(f"starts_at < {params.bind(filters.end, DateTime(timezone=True))}")
        return parts
    now = params.bind(filters.now, DateTime(timezone=True))
    return [f"ends_at < {now}" if filters.past else f"ends_at >= {now}"]


def where(
    filters: SiteFilters,
    params: Params,
    words: list[WordSql],
    *,
    skip: frozenset[str] = frozenset(),
) -> str:
    """Render the filters except those named in `skip` (`category`, `organization`, `month`)."""
    parts = _time(filters, params, with_range="month" not in skip)
    if filters.categories and "category" not in skip:
        bound = params.bind(list(filters.categories), ARRAY(String))
        parts.append(f"(category_slug = ANY({bound}) OR category_parent_slug = ANY({bound}))")
    if filters.organizations and "organization" not in skip:
        parts.append(
            f"organization_slug = ANY({params.bind(list(filters.organizations), ARRAY(String))})"
        )
    parts.extend(f"({word_match(w, TSV, TITLE_FOLDED, 'false')})" for w in words)
    return " AND ".join(parts) or "true"
