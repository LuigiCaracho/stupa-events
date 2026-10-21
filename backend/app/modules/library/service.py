"""The library list: shared documents and files of archived dossiers, and master howtos.

A view, not a store (contract 5): it lists what was shared on purpose. The right filter is a
constant part of the SQL (`visibility = 'shared'`, archived dossiers, clean files, no hidden
versions); the text filter adds to it and never replaces it. Documents are found with the
search clauses (full text plus trigram on the title), files by `ILIKE` on their name.
"""

from __future__ import annotations

from sqlalchemy import Integer, String, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.dossier import documents
from app.modules.dossier.models_documents import Document
from app.modules.dossier.rules import load_for_write
from app.modules.dossier.schemas_documents import DocumentOut
from app.modules.library.schemas import (
    LibraryCategory,
    LibraryFacets,
    LibraryItem,
    LibraryPage,
    LibrarySource,
)
from app.modules.search import clauses
from app.modules.search.filters import Filters, Reader, reader_of
from app.modules.search.params import Params
from app.modules.search.query import own_clause, year_of
from app.modules.search.schemas import FacetValue, OrgShort
from app.modules.search.words import parse
from app.shared.errors import NotFoundError
from app.shared.search import escape_like

DOC_STARTS = "coalesce(e.starts_at, d.updated_at)"
LIBRARY_KINDS = ("howto", "notes", "mail_template")
FACET_LIMIT = 20
_DOC_JOINS = (
    " FROM document d LEFT JOIN event e ON e.id = d.event_id"
    " LEFT JOIN format f ON f.id = coalesce(d.format_id, e.format_id)"
    " LEFT JOIN organization o ON o.id = coalesce(e.organization_id, f.organization_id)"
    " LEFT JOIN category c ON c.id = e.primary_category_id"
    " LEFT JOIN category cp ON cp.id = c.parent_id"
)
_FILE_JOINS = (
    " FROM attachment a JOIN event e ON e.id = a.event_id"
    " LEFT JOIN format f ON f.id = e.format_id"
    " LEFT JOIN organization o ON o.id = e.organization_id"
    " LEFT JOIN category c ON c.id = e.primary_category_id"
    " LEFT JOIN category cp ON cp.id = c.parent_id"
)
_COMMON = (
    "o.slug AS org_slug, o.short AS org_short, c.slug AS cat_slug, c.name AS cat_name,"
    " f.slug AS fmt_slug"
)


def _narrow(filters: Filters, params: Params, starts: str) -> str:
    parts = ["true"]
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


def _documents(reader: Reader, filters: Filters, params: Params, words: list) -> str:
    own = own_clause(reader, params)
    match = (
        " AND ".join(
            clauses.word_match(w, "d.search_tsv", "immutable_unaccent(d.title)", "false")
            for w in (clauses.word_sql(params, word) for word in words)
        )
        or "true"
    )
    kinds = params.bind(list(LIBRARY_KINDS), ARRAY(String))
    return (
        "SELECT 'document' AS kind, d.id, d.title, d.kind AS sub_kind,"
        " CASE WHEN d.format_id IS NOT NULL THEN 'format' ELSE 'event' END AS source_type,"
        " coalesce(d.format_id, e.id) AS source_id, coalesce(f.title, e.title) AS source_title,"
        f" e.starts_at AS source_starts, {_COMMON}, {year_of(DOC_STARTS)} AS year,"
        " d.verified_at, d.updated_at, NULL::text AS mime, NULL::bigint AS size_bytes,"
        f" coalesce(({own}), false) AS own{_DOC_JOINS}"
        " WHERE d.visibility = 'shared' AND ((d.format_id IS NOT NULL AND d.kind = 'howto')"
        f" OR (e.state = 'archived' AND d.kind = ANY({kinds})))"
        f" AND {_narrow(filters, params, DOC_STARTS)} AND {match}"
    )


def _files(reader: Reader, filters: Filters, params: Params, q: str) -> str:
    own = own_clause(reader, params)
    pattern = params.bind(f"%{escape_like(q)}%")
    name = f"a.display_name ILIKE {pattern} ESCAPE '\\'" if q else "true"
    return (
        "SELECT 'attachment' AS kind, a.id, a.display_name AS title, a.kind AS sub_kind,"
        " 'event' AS source_type, e.id AS source_id, e.title AS source_title,"
        f" e.starts_at AS source_starts, {_COMMON}, {year_of('e.starts_at')} AS year,"
        " NULL::timestamptz AS verified_at, a.created_at AS updated_at, a.mime,"
        f" a.size_bytes, coalesce(({own}), false) AS own{_FILE_JOINS}"
        " WHERE a.visibility = 'shared' AND a.scan_status = 'clean' AND a.retired_at IS NULL"
        f" AND e.state = 'archived' AND {_narrow(filters, params, 'e.starts_at')} AND {name}"
    )


def _items_cte(reader: Reader, filters: Filters, q: str, words: list, params: Params) -> str:
    branches = []
    if filters.kind != "attachment":
        branches.append(_documents(reader, filters, params, words))
    if filters.kind != "document":
        branches.append(_files(reader, filters, params, q.strip()))
    return "WITH items AS (" + " UNION ALL ".join(branches) + ")"


def _facet_sql() -> str:
    facets = (
        ("category", "cat_slug", "cat_name"),
        ("organization", "org_slug", "org_short"),
        ("year", "year::text", "year::text"),
        ("kind", "kind", "kind"),
    )
    return " UNION ALL ".join(
        f"(SELECT '{name}' AS facet, {value} AS value, min({label}) AS label, count(*) AS n"
        f" FROM items WHERE {value} IS NOT NULL GROUP BY {value}"
        f" ORDER BY n DESC, value LIMIT {FACET_LIMIT})"
        for name, value, label in facets
    )


async def list_library(
    session: AsyncSession,
    principal: Principal,
    q: str,
    filters: Filters,
    *,
    limit: int,
    offset: int,
) -> LibraryPage:
    """Return one page of the library and the facets of the filtered set (no commit)."""
    words = parse(q) if q.strip() else []
    if q.strip() and not words:
        return LibraryPage(
            items=[],
            total=0,
            limit=limit,
            offset=offset,
            facets=LibraryFacets(category=[], organization=[], year=[], kind=[]),
        )
    reader = await reader_of(session, principal)
    params = Params()
    cte = _items_cte(reader, filters, q, words, params)
    page_sql = (
        f"{cte} SELECT * FROM items ORDER BY updated_at DESC, id"
        f" LIMIT {params.bind(limit, Integer())} OFFSET {params.bind(offset, Integer())}"
    )
    total = await session.scalar(params.statement(f"{cte} SELECT count(*) FROM items")) or 0
    facet_rows = (await session.execute(params.statement(f"{cte} {_facet_sql()}"))).all()
    rows = (await session.execute(params.statement(page_sql))).all()
    grouped: dict[str, list[FacetValue]] = {
        "category": [],
        "organization": [],
        "year": [],
        "kind": [],
    }
    for row in facet_rows:
        grouped[row.facet].append(FacetValue(value=row.value, label=row.label, count=row.n))
    items = [
        LibraryItem(
            kind=r.kind,
            id=r.id,
            title=r.title,
            sub_kind=r.sub_kind,
            source=LibrarySource(
                type=r.source_type,
                id=r.source_id,
                title=r.source_title,
                starts_at=r.source_starts,
                organization=OrgShort(slug=r.org_slug, short=r.org_short),
                own=r.own,
            ),
            categories=[LibraryCategory(slug=r.cat_slug, name=r.cat_name)] if r.cat_slug else [],
            year=r.year,
            verified_at=r.verified_at,
            updated_at=r.updated_at,
            mime=r.mime,
            size_bytes=r.size_bytes,
        )
        for r in rows
    ]
    return LibraryPage(
        items=items, total=total, limit=limit, offset=offset, facets=LibraryFacets(**grouped)
    )


async def adopt(session: AsyncSession, principal: Principal, document_id, event_id) -> DocumentOut:
    """Copy a library document into a dossier (rev 1, not verified); files are never copied.

    A second howto becomes a note. Raises `NotFoundError` for a document that is not in the
    library (not shared, not of an archived dossier or format, or of a kind outside it).
    """
    doc, source = await documents.load_document(session, principal, document_id, archive=True)
    listed = (
        doc.visibility == "shared"
        and doc.kind in LIBRARY_KINDS
        and (source is None or source.state == "archived")
    )
    if not listed:
        raise NotFoundError("document not found")
    target = await load_for_write(session, principal, event_id, "event.edit")
    has_howto = await session.scalar(
        text("SELECT 1 FROM document WHERE event_id = :e AND kind = 'howto'"), {"e": target.id}
    )
    kind = "notes" if doc.kind == "howto" and has_howto else doc.kind
    copy = Document(
        event_id=target.id,
        kind=kind,
        title=doc.title,
        body_md=doc.body_md,
        meta=doc.meta,
        visibility=documents.DEFAULT_VISIBILITY[kind],
        carry_over=True,
        created_by=principal.sub,
    )
    row = await documents.insert_document(
        session, principal, target, copy, f"Aus Bibliothek übernommen: {doc.title}"
    )
    return documents.document_out(row)
