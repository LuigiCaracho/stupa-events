"""Run a search: parse, build, execute under a two second budget, shape the hits.

The statements come from `query.build`; this module executes them, adds the highlight
segments and the links, and answers a typo with a suggestion when nothing was found. A
canceled statement becomes 503 `search_timeout`.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from sqlalchemy import Row, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.formats.schemas import FormatRef
from app.modules.search import query
from app.modules.search.filters import Filters, Reader, reader_of
from app.modules.search.schemas import Facets, FacetValue, OrgShort, SearchHit, SearchOut
from app.modules.search.segments import highlight
from app.modules.search.words import parse
from app.shared.errors import ServiceUnavailableError
from app.shared.timeutil import to_local

STATEMENT_TIMEOUT = "2s"
QUERY_CANCELED = "57014"
TAB = {
    "howto": "anleitung",
    "notes": "anleitung",
    "mail_template": "mails",
    "retrospective": "nachbereitung",
}
EMPTY_FACETS = {name: [] for name, _, _ in query.FACETS}


def link_of(scope: str, row: Row[Any]) -> str:
    """Return the internal path of a hit: the dossier for own rows, the archive for foreign ones."""
    if scope == "formats":
        return f"/formate/{row.fmt_slug}"
    if scope == "events":
        return f"/dossiers/{row.id}" if row.own else f"/archiv/{row.id}"
    if row.event_id is None:
        return f"/formate/{row.fmt_slug}"
    if not row.own:
        return f"/archiv/{row.event_id}"
    return f"/dossiers/{row.event_id}/{TAB[row.doc_kind]}"


def subtitle_of(scope: str, row: Row[Any]) -> str:
    """Return the second line of a hit: organization and date, or the dossier of a document."""
    day = to_local(row.starts_at).strftime("%d.%m.%Y")
    if scope == "events":
        return f"{row.org_short} · {day}"
    if scope == "documents":
        return f"{row.event_title or row.fmt_title} · {row.org_short}"
    return row.org_short


def hit_of(scope: str, row: Row[Any], marked: dict[UUID, tuple[str, str]]) -> SearchHit:
    """Shape one page row into a hit with its highlights."""
    title, body = marked.get(row.id, ("", ""))
    kind = {"events": "event", "documents": "document", "formats": "format"}[scope]
    is_event = scope == "events"
    return SearchHit(
        kind=kind,  # type: ignore[arg-type]
        id=row.id,
        title=row.title,
        subtitle=subtitle_of(scope, row),
        state=row.state,
        starts_at=row.starts_at if is_event else None,
        organization=OrgShort(slug=row.org_slug, short=row.org_short),
        format=FormatRef(slug=row.fmt_slug, title=row.fmt_title) if row.fmt_slug else None,
        howto_verified_at=row.howto_verified_at if is_event else None,
        howto_unverified=(
            row.state == "archived" and row.howto_verified_at is None and row.has_howto
            if is_event
            else None
        ),
        foreign=not row.own,
        link=link_of(scope, row),
        rank=float(row.rank),
        highlights=[
            h
            for h in (
                highlight("title", title),
                highlight("summary" if is_event else "body", body),
            )
            if h is not None
        ],
    )


async def _marked(
    session: AsyncSession, statements: query.Statements, ids: list[UUID]
) -> dict[UUID, tuple[str, str]]:
    rows = await session.execute(statements.headlines(ids))
    return {row.id: (row.h_title, row.h_body) for row in rows}


def _facets(rows: list[Row[Any]]) -> Facets:
    grouped: dict[str, list[FacetValue]] = defaultdict(list)
    for row in rows:
        grouped[row.facet].append(FacetValue(value=row.value, label=row.label, count=row.n))
    return Facets(**{name: grouped.get(name, []) for name in EMPTY_FACETS})


async def _suggestion(session: AsyncSession, reader: Reader, q: str) -> str | None:
    long_words = [w for w in q.split() if len(w) >= query.SUGGESTION_MIN_LETTERS - 1]
    if not long_words:
        return None
    return await session.scalar(query.suggestion(reader, long_words[0]))


async def search(
    session: AsyncSession,
    principal: Principal,
    q: str,
    scope: query.Scope,
    filters: Filters,
    *,
    limit: int,
    offset: int,
) -> SearchOut:
    """Search `scope` for `q` as `principal` (no commit).

    Raises:
        ValidationProblem: `query_too_long` or `invalid_query`.
        ServiceUnavailableError: `search_timeout` after two seconds.
    """
    words = parse(q)
    if not words:
        return SearchOut(
            q=q.strip(),
            scope=scope,
            total=0,
            hits=[],
            facets=Facets(**EMPTY_FACETS),
            suggestion=None,
        )
    reader = await reader_of(session, principal)
    statements = query.build(scope, reader, filters, words, limit, offset)
    try:
        await session.execute(text(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'"))
        total = await session.scalar(statements.total) or 0
        facets = _facets(list((await session.execute(statements.facets)).all()))
        rows = list((await session.execute(statements.page)).all())
        marked = await _marked(session, statements, [r.id for r in rows]) if rows else {}
        suggestion = None if total else await _suggestion(session, reader, q.strip())
    except DBAPIError as exc:
        if getattr(exc.orig, "sqlstate", None) != QUERY_CANCELED:
            raise
        raise ServiceUnavailableError(
            "Die Suche hat zu lange gedauert.", code="search_timeout"
        ) from exc
    return SearchOut(
        q=q.strip(),
        scope=scope,
        total=total,
        hits=[hit_of(scope, row, marked) for row in rows],
        facets=facets,
        suggestion=suggestion,
    )
