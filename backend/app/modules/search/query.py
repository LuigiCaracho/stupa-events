"""Build the search statements: one place for the right filter (contract 6.2).

`build` returns the `Statements` of one search: the hits CTE and its five uses (total, facets,
page, headlines, suggestion). The right filter is the first condition of every base query and
cannot be left out by any scope or filter; the template list and the library call the same
builders, so the rule exists once. Every value is a bound parameter; the SQL text holds
only column names, constants and placeholders.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import Integer, String, TextClause, Uuid, bindparam
from sqlalchemy.dialects.postgresql import ARRAY

from app.modules.search import clauses
from app.modules.search.clauses import CFG, DOCUMENT_FACTOR, NAME_FACTOR, WordSql
from app.modules.search.filters import Filters, Reader
from app.modules.search.params import Params
from app.modules.search.segments import HEADLINE_OPTIONS, TITLE_HEADLINE_OPTIONS
from app.modules.search.words import Word
from app.shared.timeutil import DEFAULT_TZID

type Scope = Literal["events", "documents", "formats"]
FACET_LIMIT = 20
DOC_STARTS = "coalesce(e.starts_at, d.updated_at)"
BODY_CHARS = 50_000
SOURCE = {
    "events": ("event", "e", "summary"),
    "documents": ("document", "d", "body_md"),
    "formats": ("format", "f", "description_md"),
}
FACETS = (
    ("state", "state", "state"),
    ("organization", "org_slug", "org_short"),
    ("year", "year::text", "year::text"),
    ("category", "cat_slug", "cat_name"),
    ("format", "fmt_slug", "fmt_title"),
)


def year_of(column: str) -> str:
    return f"EXTRACT(YEAR FROM timezone('{DEFAULT_TZID}', {column}))::int"


@dataclass(frozen=True, slots=True)
class Spec:
    """A scope: its base query and the extra condition and rank of one word."""

    base: str
    extra_match: Callable[[WordSql], str]
    extra_rank: Callable[[WordSql], str]


@dataclass(frozen=True, slots=True)
class Statements:
    """The statements of one search; they share the bound parameters of one `Params`."""

    total: TextClause
    facets: TextClause
    page: TextClause
    headline_sql: str
    params: Params

    def headlines(self, ids: list[UUID]) -> TextClause:
        """The statement that marks the hits in the title and the body of the page rows."""
        return self.params.statement(self.headline_sql).bindparams(
            bindparam("ids", ids, type_=ARRAY(Uuid))
        )


def own_clause(reader: Reader, params: Params) -> str:
    if reader.scope is None:
        return "true"
    return (
        f"(e.organization_id = ANY({clauses.uuid_array(params, reader.scope)})"
        f" OR (e.organization_id IS NULL AND e.created_by = {params.bind(reader.sub)}))"
    )


def _visible(reader: Reader, filters: Filters, params: Params) -> str:
    own = own_clause(reader, params)
    if filters.clonable:
        return f"(e.state = 'archived' OR ({own} AND e.state IN ('live', 'followup')))"
    return f"({own} OR e.state = 'archived')"


def _filters(filters: Filters, params: Params, *, state: str, starts: str) -> str:
    parts = ["true"]
    if filters.states:
        parts.append(f"{state} = ANY({params.bind(list(filters.states), ARRAY(String))})")
    if filters.org:
        parts.append(f"o.slug = {params.bind(filters.org)}")
    if filters.year:
        parts.append(f"{year_of(starts)} = {params.bind(filters.year, Integer())}")
    if filters.category:
        bound = params.bind(filters.category)
        parts.append(f"(c.slug = {bound} OR cp.slug = {bound})")
    if filters.format:
        parts.append(f"f.slug = {params.bind(filters.format)}")
    return " AND ".join(parts)


_EVENT_COLUMNS = (
    "e.id, e.title, immutable_unaccent(e.title) AS title_u, e.summary AS body, e.state,"
    " e.starts_at, e.search_tsv AS tsv, e.organization_id, o.slug AS org_slug,"
    " o.name AS org_name, o.short AS org_short, f.slug AS fmt_slug, f.title AS fmt_title,"
    " c.id AS cat_id, c.slug AS cat_slug, c.name AS cat_name, c.kind AS cat_kind,"
    " e.howto_verified_at, (e.outcome ->> 'attendance')::int AS attendance,"
    " f.last_verified_at AS fmt_verified_at,"
    " (SELECT count(*) FROM document sd WHERE sd.event_id = e.id AND sd.visibility = 'shared'"
    " AND sd.kind IN ('howto', 'notes', 'mail_template'))::int AS shared_docs,"
    " (SELECT count(*) FROM checklist_item ci WHERE ci.event_id = e.id)::int AS checklist_n,"
    " e.all_day,"
    " (EXISTS (SELECT 1 FROM document h WHERE h.event_id = e.id AND h.kind = 'howto')"
    " OR f.master_howto_document_id IS NOT NULL) AS has_howto,"
    f" {year_of('e.starts_at')} AS year,"
    " NULL::text AS doc_kind, NULL::uuid AS event_id, NULL::text AS event_title,"
    f" to_tsvector({CFG}, concat_ws(' ', o.name, o.short, v.name)) AS names_tsv"
)
_EVENT_FROM = (
    " FROM event e LEFT JOIN organization o ON o.id = e.organization_id"
    " LEFT JOIN format f ON f.id = e.format_id"
    " LEFT JOIN category c ON c.id = e.primary_category_id"
    " LEFT JOIN category cp ON cp.id = c.parent_id"
    " LEFT JOIN venue v ON v.id = e.venue_id"
)


def events_spec(reader: Reader, filters: Filters, params: Params) -> Spec:
    """The dossiers: own ones in every state, foreign ones only when archived."""
    own = own_clause(reader, params)
    base = (
        f"SELECT {_EVENT_COLUMNS}, ({own}) AS own{_EVENT_FROM}"
        f" WHERE {_visible(reader, filters, params)}"
        f" AND {_filters(filters, params, state='e.state', starts='e.starts_at')}"
    )
    visible = clauses.document_visible(reader, params, "base.own", "base.organization_id")
    documents = f"FROM document d WHERE d.event_id = base.id AND {visible}"

    def match(word: WordSql) -> str:
        return (
            f"(base.names_tsv @@ {word.tsquery}"
            f" OR EXISTS (SELECT 1 {documents} AND d.search_tsv @@ {word.tsquery}))"
        )

    def rank(word: WordSql) -> str:
        return (
            f"{NAME_FACTOR} * CASE WHEN base.names_tsv @@ {word.tsquery}"
            f" THEN ts_rank(base.names_tsv, {word.tsquery}) ELSE 0 END"
            f" + {DOCUMENT_FACTOR} * coalesce((SELECT max(ts_rank(d.search_tsv, {word.tsquery}))"
            f" {documents}), 0)"
        )

    return Spec(base, match, rank)


def documents_spec(reader: Reader, filters: Filters, params: Params) -> Spec:
    """The documents: readable ones of readable dossiers, and the shared master howtos."""
    own = own_clause(reader, params)
    visible = clauses.document_visible(reader, params, own, "e.organization_id")
    base = (
        "SELECT d.id, d.title, immutable_unaccent(d.title) AS title_u, d.body_md AS body,"
        " e.state, coalesce(e.starts_at, d.updated_at) AS starts_at, d.search_tsv AS tsv,"
        " e.organization_id, o.slug AS org_slug, o.name AS org_name, o.short AS org_short,"
        " f.slug AS fmt_slug, f.title AS fmt_title, c.id AS cat_id, c.slug AS cat_slug,"
        " c.name AS cat_name, c.kind AS cat_kind, NULL::timestamptz AS howto_verified_at,"
        " NULL::int AS attendance, NULL::timestamptz AS fmt_verified_at, NULL::int AS shared_docs,"
        " NULL::int AS checklist_n, false AS all_day, false AS has_howto,"
        f" {year_of(DOC_STARTS)} AS year, d.kind AS doc_kind,"
        " e.id AS event_id, e.title AS event_title, NULL::tsvector AS names_tsv,"
        f" coalesce(({own}), false) AS own"
        " FROM document d LEFT JOIN event e ON e.id = d.event_id"
        " LEFT JOIN format f ON f.id = coalesce(d.format_id, e.format_id)"
        " LEFT JOIN organization o ON o.id = coalesce(e.organization_id, f.organization_id)"
        " LEFT JOIN category c ON c.id = e.primary_category_id"
        " LEFT JOIN category cp ON cp.id = c.parent_id"
        " WHERE ((d.format_id IS NOT NULL AND d.visibility = 'shared')"
        f" OR (d.event_id IS NOT NULL AND ({own} OR e.state = 'archived') AND {visible}))"
        f" AND {_filters(filters, params, state='e.state', starts=DOC_STARTS)}"
    )
    return Spec(base, lambda word: "false", lambda word: "0")


def formats_spec(reader: Reader, filters: Filters, params: Params) -> Spec:
    """The active formats, readable for everybody who may search."""
    narrowed = _filters(Filters(org=filters.org), params, state="NULL", starts="f.created_at")
    base = (
        "SELECT f.id, f.title, immutable_unaccent(f.title) AS title_u, f.description_md AS body,"
        " NULL::text AS state, f.created_at AS starts_at, f.search_tsv AS tsv,"
        " f.organization_id, o.slug AS org_slug, o.name AS org_name, o.short AS org_short,"
        " f.slug AS fmt_slug, f.title AS fmt_title, NULL::uuid AS cat_id,"
        " NULL::text AS cat_slug, NULL::text AS cat_name, NULL::text AS cat_kind,"
        " f.last_verified_at AS howto_verified_at, NULL::int AS attendance,"
        " f.last_verified_at AS fmt_verified_at, NULL::int AS shared_docs,"
        " NULL::int AS checklist_n, false AS all_day, false AS has_howto, NULL::int AS year,"
        " NULL::text AS doc_kind,"
        " NULL::uuid AS event_id, NULL::text AS event_title, NULL::tsvector AS names_tsv,"
        " true AS own FROM format f JOIN organization o ON o.id = f.organization_id"
        f" WHERE f.active AND {narrowed}"
    )
    return Spec(base, lambda word: "false", lambda word: "0")


SPECS: dict[str, Callable[[Reader, Filters, Params], Spec]] = {
    "events": events_spec,
    "documents": documents_spec,
    "formats": formats_spec,
}


def hits_cte(spec: Spec, words: list[WordSql]) -> str:
    """The `WITH` clause that selects the matching rows and ranks them (all rows for no words)."""
    match = (
        " AND ".join(
            clauses.word_match(w, "base.tsv", "base.title_u", spec.extra_match(w)) for w in words
        )
        or "true"
    )
    rank = (
        " + ".join(
            clauses.word_rank(w, "base.tsv", "base.title_u", "base.title", spec.extra_rank(w))
            for w in words
        )
        or "0"
    )
    return (
        f"WITH base AS ({spec.base}), hits AS (SELECT base.*, ({rank}) AS rank"
        f" FROM base WHERE {match})"
    )


def _facet_sql() -> str:
    parts = [
        f"(SELECT '{name}' AS facet, {value} AS value, min({label}) AS label, count(*) AS n"
        f" FROM hits WHERE {value} IS NOT NULL GROUP BY {value}"
        f" ORDER BY n DESC, value LIMIT {FACET_LIMIT})"
        for name, value, label in FACETS
    ]
    return " UNION ALL ".join(parts)


ORDER = {
    "rank": "rank DESC, starts_at DESC NULLS LAST, id",
    "template": "rank DESC, fmt_verified_at DESC NULLS LAST, starts_at DESC, id",
}


def build(
    scope: Scope,
    reader: Reader,
    filters: Filters,
    words: list[Word],
    limit: int,
    offset: int,
    order: Literal["rank", "template"] = "rank",
) -> Statements:
    """Build all statements of a search over `scope` for `reader`.

    Without words every readable row matches (the template list and the library use that).
    """
    params = Params()
    spec = SPECS[scope](reader, filters, params)
    sql_words = [clauses.word_sql(params, w) for w in words]
    cte = hits_cte(spec, sql_words)
    table, alias, body = SOURCE[scope]
    combined = " || ".join(w.tsquery for w in sql_words) or "''::tsquery"
    options = params.bind(HEADLINE_OPTIONS)
    title_options = params.bind(TITLE_HEADLINE_OPTIONS)
    headline = "ts_headline({cfg}, replace(replace({text}, chr(1), ''), chr(2), ''), ({q}), {o})"
    page = (
        f"{cte} SELECT * FROM hits ORDER BY {ORDER[order]}"
        f" LIMIT {params.bind(limit, Integer())} OFFSET {params.bind(offset, Integer())}"
    )
    title_head = headline.format(cfg=CFG, text=f"{alias}.title", q=combined, o=title_options)
    body_text = f"left(coalesce({alias}.{body}, chr(32)), {BODY_CHARS})"
    body_head = headline.format(cfg=CFG, text=body_text, q=combined, o=options)
    headlines = (
        f"SELECT {alias}.id, {title_head} AS h_title, {body_head} AS h_body"
        f" FROM {table} {alias} WHERE {alias}.id = ANY(:ids)"
    )
    return Statements(
        total=params.statement(f"{cte} SELECT count(*) FROM hits"),
        facets=params.statement(f"{cte} {_facet_sql()}"),
        page=params.statement(page),
        headline_sql=headlines,
        params=params,
    )


SUGGESTION_WINDOW = (0.3, 0.5)
SUGGESTION_MIN_LETTERS = 5


def suggestion(reader: Reader, word: str) -> TextClause:
    """Find the title word (five letters or more) most similar to a typo, within 0.3 to 0.5.

    The words come from the titles of readable dossiers and the active formats only. Below
    0.3 a word is noise; from 0.5 on the search itself would have found it.
    """
    params = Params()
    folded = f"immutable_unaccent(lower({params.bind(word)}))"
    low, high = SUGGESTION_WINDOW
    own = own_clause(reader, params)
    sql = (
        "SELECT w FROM (SELECT DISTINCT tw AS w FROM ("
        "SELECT regexp_split_to_table(e.title, '[^[:alnum:]äöüßÄÖÜ]+') AS tw FROM event e"
        f" WHERE {own} OR e.state = 'archived'"
        " UNION ALL SELECT regexp_split_to_table(f.title, '[^[:alnum:]äöüßÄÖÜ]+')"
        " FROM format f WHERE f.active) t"
        f" WHERE length(tw) >= {SUGGESTION_MIN_LETTERS}) x"
        f" WHERE word_similarity({folded}, immutable_unaccent(lower(w))) >= {low}"
        f" AND word_similarity({folded}, immutable_unaccent(lower(w))) < {high}"
        f" ORDER BY word_similarity({folded}, immutable_unaccent(lower(w))) DESC, w LIMIT 1"
    )
    return params.statement(sql)
