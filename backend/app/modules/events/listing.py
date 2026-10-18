"""The filters and queries of `GET /events`: list view and board view."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.access import visible_events_query
from app.modules.events.board import (
    ACTIVE_COLUMNS,
    COLUMNS,
    DESCENDING_COLUMNS,
)
from app.modules.events.card_schemas import BoardColumn, BoardOut, ColumnKey
from app.modules.events.cards import present_cards
from app.modules.events.models import Event
from app.modules.orgs.models import Organization
from app.modules.taxonomy.models import Category
from app.shared.search import escape_like
from app.shared.timeutil import DEFAULT_TZID, utcnow


@dataclass(frozen=True, slots=True)
class Filters:
    """The query parameters of the list and the board."""

    states: tuple[str, ...] = ()
    organization: str | None = None
    category: str | None = None
    mine: bool = False
    q: str | None = None
    start: date | None = None
    end: date | None = None


def _local_start(day: date) -> datetime:
    return datetime.combine(day, time.min, ZoneInfo(DEFAULT_TZID)).astimezone(UTC)


def apply_filters(query: Select, filters: Filters, principal: Principal) -> Select:
    """Narrow `query` by the filters, all in SQL."""
    if filters.states:
        query = query.where(Event.state.in_(filters.states))
    if filters.organization:
        slug = select(Organization.id).where(Organization.slug == filters.organization)
        query = query.where(Event.organization_id == slug.scalar_subquery())
    if filters.category:
        root = select(Category.id).where(Category.slug == filters.category).scalar_subquery()
        family = select(Category.id).where(or_(Category.id == root, Category.parent_id == root))
        query = query.where(Event.primary_category_id.in_(family))
    if filters.mine:
        query = query.where(
            or_(Event.created_by == principal.sub, Event.submitted_by == principal.sub)
        )
    if filters.q:
        pattern = f"%{escape_like(filters.q.strip())}%"
        query = query.where(
            or_(Event.title.ilike(pattern, escape="\\"), Event.summary.ilike(pattern, escape="\\"))
        )
    if filters.start:
        query = query.where(Event.starts_at >= _local_start(filters.start))
    if filters.end:
        query = query.where(Event.starts_at < _local_start(filters.end + timedelta(days=1)))
    return query


async def list_cards(
    session: AsyncSession,
    principal: Principal,
    filters: Filters,
    *,
    descending: bool,
    limit: int,
    offset: int,
):  # noqa: ANN201
    """Return `(cards, total)` of the readable dossiers that match the filters."""
    query = apply_filters(await visible_events_query(session, principal), filters, principal)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    order = (Event.starts_at.desc(), Event.id) if descending else (Event.starts_at, Event.id)
    rows = await session.scalars(query.order_by(*order).limit(limit).offset(offset))
    return await present_cards(session, principal, list(rows)), total


def _column_keys(filters: Filters) -> tuple[ColumnKey, ...]:
    closed: tuple[ColumnKey, ...] = tuple(
        key for key in ("archived", "withdrawn") if key in filters.states
    )
    return closed or ACTIVE_COLUMNS


async def board(
    session: AsyncSession, principal: Principal, filters: Filters, *, column_limit: int
) -> BoardOut:
    """Build the board: per column the total and the first `column_limit` cards."""
    base = await visible_events_query(session, principal)
    columns = []
    for key in _column_keys(filters):
        states = tuple(s for s in COLUMNS[key] if not filters.states or s in filters.states)
        if not states:
            columns.append(
                BoardColumn(key=key, states=list(COLUMNS[key]), total=0, items=[], truncated=False)
            )
            continue
        query = apply_filters(base, replace(filters, states=states), principal)
        total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
        order = (
            (Event.starts_at.desc(), Event.id)
            if key in DESCENDING_COLUMNS
            else (Event.starts_at, Event.id)
        )
        rows = await session.scalars(query.order_by(*order).limit(column_limit))
        cards = await present_cards(session, principal, list(rows))
        columns.append(
            BoardColumn(
                key=key,
                states=list(COLUMNS[key]),
                total=total,
                items=cards,
                truncated=total > len(cards),
            )
        )
    return BoardOut(columns=columns, generated_at=utcnow())
