"""The in-memory half of the text search: filters, disjunctive facets, paging, SQL text."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from app.modules.publicapi.query import memory
from app.modules.publicapi.query.filters import SiteFilters
from app.modules.publicapi.query.search import Position, decode_position
from app.modules.search.words import parse
from tests.unit.publicapi.test_public_unit import row

NOW = datetime(2026, 10, 22, 12, tzinfo=UTC)


def hit(
    n: int, *, org: str = "fsi", cat: str = "kino", parent: str | None = None, **over: Any
) -> Any:
    base = row(
        id=__import__("uuid").UUID(int=n),
        slug=f"e-{n}",
        organization_slug=org,
        organization_name=org.upper(),
        organization_short=org.upper(),
        category_slug=cat,
        category_name=cat.title(),
        category_parent_slug=parent,
        category_parent_name=parent.title() if parent else None,
        category_parent_kind="fachschaft" if parent else None,
        starts_at=datetime(2026, 11, n, 18, tzinfo=UTC),
        ends_at=datetime(2026, 11, n, 20, tzinfo=UTC),
    )
    return SimpleNamespace(**{**vars(base), "rank": 1.0 - n / 100, **over})


ROWS = [
    hit(1),
    hit(2, org="makers", cat="party"),
    hit(3, cat="fsi", parent="fachschaft"),
    hit(
        4,
        org="makers",
        cat="kino",
        starts_at=datetime(2026, 12, 4, 18, tzinfo=UTC),
        ends_at=datetime(2026, 12, 4, 20, tzinfo=UTC),
    ),
]


def test_select_applies_each_filter_and_skips_on_request() -> None:
    filters = SiteFilters(now=NOW, categories=("kino",), organizations=("makers",))
    assert [r.slug for r in memory.select(ROWS, filters)] == ["e-4"]
    assert len(memory.select(ROWS, filters, skip=frozenset({"category"}))) == 2
    assert len(memory.select(ROWS, filters, skip=frozenset({"organization"}))) == 2
    parent = SiteFilters(now=NOW, categories=("fachschaft",))
    assert [r.slug for r in memory.select(ROWS, parent)] == ["e-3"]
    ranged = SiteFilters(
        now=NOW,
        start=datetime(2026, 12, 1, tzinfo=UTC),
        end=datetime(2027, 1, 1, tzinfo=UTC),
    )
    assert [r.slug for r in memory.select(ROWS, ranged)] == ["e-4"]
    assert len(memory.select(ROWS, ranged, skip=frozenset({"month"}))) == 4


def test_facets_count_over_every_filter_but_their_own() -> None:
    filters = SiteFilters(now=NOW, categories=("kino",), organizations=("fsi",))
    cats = {c.slug: c.count for c in memory._category_facets(ROWS, filters)}
    assert cats == {"kino": 1, "fsi": 1, "fachschaft": 1}
    orgs = {o.slug: o.count for o in memory._organization_facets(ROWS, filters)}
    assert orgs == {"fsi": 1, "makers": 1}
    months = [(m.month, m.count) for m in memory._month_facets(ROWS, filters)]
    assert months == [("2026-11", 1)]


def test_months_run_forward_and_past_listings_backward() -> None:
    forward = memory._month_facets(ROWS, SiteFilters(now=NOW))
    assert [m.month for m in forward] == ["2026-11", "2026-12"]
    backward = memory._month_facets(ROWS, SiteFilters(now=NOW, past=True))
    assert [m.month for m in backward] == ["2026-12", "2026-11"]


class FakeSession:
    def __init__(self, rows: list[Any]) -> None:
        self.rows, self.sql = rows, []

    async def execute(self, statement: Any, *_: Any) -> Any:
        self.sql.append(str(statement))
        rows = self.rows

        class Result:
            def all(self) -> list[Any]:
                return rows

        return Result()


async def test_search_pages_with_an_offset_and_counts_only_on_the_first_page() -> None:
    filters = SiteFilters(now=NOW, words=tuple(parse("kino")))
    session = FakeSession(ROWS)
    first = await memory.search(session, filters, Position(), 2, first=True)  # type: ignore[arg-type]
    assert [c.slug for c in first.items] == ["e-1", "e-2"] and first.total == 4
    assert first.facets is not None and first.next_cursor is not None
    assert decode_position(first.next_cursor, text=True).offset == 2
    last = await memory.search(session, filters, Position(offset=2), 2, first=False)  # type: ignore[arg-type]
    assert [c.slug for c in last.items] == ["e-3", "e-4"]
    assert last.total is None and last.facets is None and last.next_cursor is None


async def test_the_cursor_stops_at_the_offset_cap() -> None:
    many = [hit(1, rank=1.0)] * 400
    filters = SiteFilters(now=NOW, words=tuple(parse("kino")))
    page = await memory.search(FakeSession(many), filters, Position(offset=200), 50, first=False)  # type: ignore[arg-type]
    assert page.next_cursor is None


def test_the_scan_sql_has_a_cap_and_binds_the_words() -> None:
    sql, params = memory.hits_sql(SiteFilters(now=NOW, words=tuple(parse("Kino'; DROP"))))
    assert f"LIMIT {memory.HIT_CAP}" in sql and "DROP" not in sql and "ORDER BY rank DESC" in sql
    assert params.statement(sql).compile().params


def test_events_without_a_category_count_in_no_category_facet() -> None:
    bare = hit(5, category_slug=None, category_name=None)
    filters = SiteFilters(now=NOW)
    facets = memory._category_facets([bare, ROWS[0]], filters)
    assert [(f.slug, f.count) for f in facets] == [("kino", 1)]


def test_a_cursor_outside_the_database_years_is_invalid() -> None:
    import pytest

    from app.modules.publicapi import cursor
    from app.shared.errors import ValidationProblem

    early = cursor.encode(datetime(1, 1, 3, tzinfo=UTC), __import__("uuid").UUID(int=1))
    with pytest.raises(ValidationProblem):
        cursor.decode(early)
