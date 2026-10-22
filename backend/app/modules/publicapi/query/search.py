"""Ranked text search and keyset paging on `public_event_v` (contract 2.2.1 to 2.2.3).

Without text the order is `(starts_at, id)` and the cursor a keyset; with text the order is
the rank and the cursor an offset capped at 200, because a float rank is no keyset. The rank
and the match come from the same string builders as the internal search.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import DateTime, Row, Uuid
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi import cursor as cursors
from app.modules.publicapi.query.columns import CARD
from app.modules.publicapi.query.filters import TITLE_FOLDED, TSV, SiteFilters, where
from app.modules.search.clauses import WordSql, word_rank
from app.modules.search.params import Params
from app.shared.errors import FieldError, ValidationProblem

MAX_OFFSET = 200
RANK_TITLE = "title"


@dataclass(frozen=True, slots=True)
class Position:
    """Where a page starts: a keyset (no text) or an offset (text)."""

    keyset: cursors.Cursor | None = None
    offset: int = 0


def encode_offset(offset: int) -> str:
    """Return the cursor of a text search that continues at `offset`."""
    return base64.urlsafe_b64encode(json.dumps({"o": offset}).encode()).decode()


def decode_position(raw: str | None, *, text: bool) -> Position:
    """Read a cursor of the form the request needs.

    Raises:
        ValidationProblem: `invalid_cursor` for the other form or for anything foreign.
    """
    if not raw:
        return Position()
    try:
        if text:
            offset = json.loads(base64.urlsafe_b64decode(raw.encode()))["o"]
            if not isinstance(offset, int) or not 0 <= offset <= MAX_OFFSET:
                raise ValueError("offset")
            return Position(offset=offset)
        return Position(keyset=cursors.decode(raw))
    except (ValueError, KeyError, TypeError, binascii.Error):
        raise ValidationProblem(
            "Invalid cursor.",
            code="invalid_cursor",
            errors=[FieldError(field="cursor", msg="invalid")],
        ) from None


def rank_sql(words: list[WordSql]) -> str:
    """The summed rank of all words."""
    return " + ".join(word_rank(w, TSV, TITLE_FOLDED, RANK_TITLE, "0") for w in words)


def _keyset(position: Position, params: Params, descending: bool) -> str:
    if position.keyset is None:
        return ""
    after = params.bind(position.keyset.starts_at, DateTime(timezone=True))
    ident = params.bind(position.keyset.id, Uuid())
    op = "<" if descending else ">"
    return f" AND (starts_at, id) {op} ({after}, {ident})"


async def page(
    session: AsyncSession, filters: SiteFilters, position: Position, limit: int
) -> tuple[list[Row[Any]], str | None]:
    """Read one keyset page without text and the cursor of the next one."""
    params = Params()
    condition = where(filters, params, [])
    order = "DESC" if filters.descending else "ASC"
    sql = (
        f"SELECT {CARD} FROM public_event_v WHERE {condition}"
        f"{_keyset(position, params, filters.descending)}"
        f" ORDER BY starts_at {order}, id {order} LIMIT {limit + 1}"
    )
    rows = list((await session.execute(params.statement(sql))).all())
    shown = rows[:limit]
    if len(rows) <= limit:
        return shown, None
    last = shown[-1]
    return shown, cursors.encode(last.starts_at, last.id)
