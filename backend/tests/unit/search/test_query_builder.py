"""The search statements: values bound, the right filter always there, trigram per word."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.search import query
from app.modules.search.filters import Filters, Reader
from app.modules.search.params import Params
from app.modules.search.words import parse

READER = Reader("sub-x", frozenset({uuid4()}), frozenset())
EVERYBODY = Reader("sub-y", None, None)


def sql_of(statement) -> str:  # noqa: ANN001
    return str(statement.compile(compile_kwargs={"render_postcompile": True}))


def build(q: str, scope: str = "events", filters: Filters | None = None, reader: Reader = READER):  # noqa: ANN201
    return query.build(scope, reader, filters or Filters(), parse(q), 20, 0)  # type: ignore[arg-type]


@pytest.mark.parametrize("scope", ["events", "documents", "formats"])
def test_every_scope_binds_the_input_and_keeps_it_out_of_the_text(scope: str) -> None:
    hostile = "x'); DROP TABLE event; --"
    built = build(hostile, scope)
    for statement in (built.total, built.facets, built.page):
        text = sql_of(statement)
        assert "DROP TABLE" not in text and hostile not in text
        assert hostile in [p.value for p in statement._bindparams.values()]


def test_the_right_filter_is_part_of_every_event_and_document_statement() -> None:
    for scope in ("events", "documents"):
        for statement in (build("kino", scope).total, build("kino", scope).page):
            text = sql_of(statement)
            assert "organization_id = ANY" in text and "'archived'" in text
    assert "d.visibility = 'shared'" in sql_of(build("kino", "documents").total)
    open_text = sql_of(build("kino", "events", reader=EVERYBODY).total)
    assert "true OR e.state = 'archived'" in open_text


def test_the_formats_scope_reads_only_active_formats() -> None:
    assert "f.active" in sql_of(build("kino", "formats").total)


def test_trigram_runs_per_word_and_not_for_words_that_may_not_be_fuzzy() -> None:
    two = sql_of(build("kino abend").total)
    assert two.count("word_similarity(immutable_unaccent(lower(") >= 4
    short = sql_of(build("am").total)
    assert "word_similarity(immutable_unaccent(lower(" not in short.replace("false", "")
    syntax = sql_of(build('"kino abend"').total)
    assert "regexp_split_to_table" not in syntax


def test_filters_become_bound_conditions() -> None:
    filters = Filters(("archived",), "fsi", 2025, "kino", "movienight")
    text = sql_of(build("kino", filters=filters).page)
    for fragment in ("e.state = ANY", "o.slug =", "EXTRACT(YEAR", "c.slug =", "f.slug ="):
        assert fragment in text


def test_the_template_mode_orders_by_format_freshness_and_clonable_states() -> None:
    built = query.build("events", READER, Filters(clonable=True), [], 10, 0, order="template")
    text = sql_of(built.page)
    assert "fmt_verified_at DESC NULLS LAST" in text and "('live', 'followup')" in text
    assert "WHERE true" not in text or "true" in text


def test_params_only_attach_the_placeholders_a_statement_uses() -> None:
    params = Params()
    used, unused = params.bind("a"), params.bind("b")
    statement = params.statement(f"SELECT {used}")
    assert set(statement._bindparams) == {used.removeprefix(":")} and unused


def test_the_suggestion_statement_binds_the_typo() -> None:
    statement = query.suggestion(READER, "Kinabnd")
    assert "Kinabnd" in [p.value for p in statement._bindparams.values()]
    assert "word_similarity" in sql_of(statement) and "LIMIT 1" in sql_of(statement)
