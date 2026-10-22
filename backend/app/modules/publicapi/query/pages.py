"""The queries behind the site routes: detail, today, categories, calendar and archive.

Each function reads `public_event_v` or `public_category_v` on the public session and returns
a finished wire model. The routes cache and rate-limit around them.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import Row, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi import cursor as cursors
from app.modules.publicapi.clock import (
    berlin_date,
    day_end,
    day_start,
    month_bounds,
)
from app.modules.publicapi.query import cards
from app.modules.publicapi.query.columns import CARD, FULL
from app.modules.publicapi.site_schemas import (
    PublicArchiveOut,
    PublicCalendarDay,
    PublicCalendarOut,
    PublicCategoryOut,
    PublicEventCard,
    PublicEventDetail,
    PublicTodayDay,
    PublicTodayOut,
)

TODAY_CAP, TODAY_DAYS, CALENDAR_CAP, MORE_CAP = 100, 7, 300, 4
ARCHIVE_DEFAULT_LIMIT = 24


async def event_row(session: AsyncSession, slug: str) -> Row[Any] | None:
    """Read one public event by slug (past events included), or `None`."""
    sql = text(f"SELECT {FULL} FROM public_event_v WHERE slug = :slug")
    return (await session.execute(sql, {"slug": slug})).first()


async def detail(session: AsyncSession, row: Row[Any], now: datetime) -> PublicEventDetail:
    """Build the detail page; `more` are up to four later events of the same format."""
    more: list[PublicEventCard] = []
    if row.format_slug:
        sql = text(
            f"SELECT {CARD} FROM public_event_v WHERE format_slug = :format AND slug <> :slug"
            f" AND ends_at >= :now ORDER BY starts_at, id LIMIT {MORE_CAP}"
        )
        found = await session.execute(
            sql, {"format": row.format_slug, "slug": row.slug, "now": now}
        )
        more = [cards.to_card(r) for r in found.all()]
    return cards.to_detail(row, now, more)


async def today(session: AsyncSession, now: datetime) -> PublicTodayOut:
    """Today at the campus (the whole Berlin day) and the seven days after it."""
    day = berlin_date(now)
    sql = text(
        f"SELECT {CARD} FROM public_event_v WHERE ends_at > :start AND starts_at < :end"
        f" ORDER BY starts_at, id LIMIT {TODAY_CAP + 1}"
    )
    found = (
        await session.execute(
            sql, {"start": day_start(day), "end": day_end(day + timedelta(days=TODAY_DAYS))}
        )
    ).all()
    truncated = len(found) > TODAY_CAP
    ending = day_end(day)
    current = [cards.to_card(r) for r in found[:TODAY_CAP] if r.starts_at < ending]
    later: dict[date, list[PublicEventCard]] = {}
    for r in found[:TODAY_CAP]:
        if r.starts_at >= ending:
            later.setdefault(berlin_date(r.starts_at), []).append(cards.to_card(r))
    return PublicTodayOut(
        generated_at=now,
        date=day,
        today=current,
        days=[PublicTodayDay(date=d, items=items) for d, items in sorted(later.items())],
        truncated=truncated,
    )


async def categories(session: AsyncSession, now: datetime) -> list[PublicCategoryOut]:
    """List the active categories, parents first, with the number of upcoming events."""
    sql = text(
        "SELECT c.slug, c.name, c.kind, c.parent_slug, c.description,"
        " (SELECT count(*) FROM public_event_v e WHERE e.ends_at >= :now"
        "  AND (e.category_slug = c.slug OR e.category_parent_slug = c.slug)) AS upcoming"
        " FROM public_category_v c WHERE c.active"
        " ORDER BY (c.parent_slug IS NOT NULL), c.sort, c.name"
    )
    return [
        PublicCategoryOut(
            slug=r.slug,
            name=r.name,
            kind=r.kind,
            parent_slug=r.parent_slug,
            description=r.description,
            upcoming_count=r.upcoming,
        )
        for r in (await session.execute(sql, {"now": now})).all()
    ]


def _days_touched(row: Row[Any], first: date, last: date) -> list[date]:
    start = berlin_date(row.starts_at)
    end = (
        berlin_date(row.ends_at - timedelta(microseconds=1))
        if row.ends_at > row.starts_at
        else start
    )
    return [
        start + timedelta(days=n)
        for n in range((end - start).days + 1)
        if first <= start + timedelta(days=n) <= last
    ]


async def calendar(
    session: AsyncSession, year: int, month: int, category: str | None
) -> PublicCalendarOut:
    """One Berlin month: every event on each day it touches, at most 300 events."""
    begin, end = month_bounds(year, month)
    condition = "ends_at > :begin AND starts_at < :end"
    values: dict[str, Any] = {"begin": begin, "end": end}
    if category:
        condition += " AND (category_slug = :category OR category_parent_slug = :category)"
        values["category"] = category
    sql = text(
        f"SELECT {CARD} FROM public_event_v WHERE {condition}"
        f" ORDER BY starts_at, id LIMIT {CALENDAR_CAP + 1}"
    )
    found = (await session.execute(sql, values)).all()
    first, last = berlin_date(begin), berlin_date(end - timedelta(microseconds=1))
    by_day: dict[date, list[Row[Any]]] = {}
    for row in found[:CALENDAR_CAP]:
        for day in _days_touched(row, first, last):
            by_day.setdefault(day, []).append(row)
    return PublicCalendarOut(
        month=f"{year:04d}-{month:02d}",
        truncated=len(found) > CALENDAR_CAP,
        days=[
            PublicCalendarDay(date=d, count=len(rows), items=[cards.to_entry(r) for r in rows])
            for d, rows in sorted(by_day.items())
        ],
    )


async def archive(
    session: AsyncSession,
    now: datetime,
    year: int | None,
    category: str | None,
    limit: int,
    cursor: cursors.Cursor | None,
) -> PublicArchiveOut:
    """Past events with a poster of one year, newest first."""
    base = "ends_at < :now AND hero_sha IS NOT NULL"
    values: dict[str, Any] = {"now": now}
    if category:
        base += " AND (category_slug = :category OR category_parent_slug = :category)"
        values["category"] = category
    year_rows = await session.execute(
        text(
            "SELECT DISTINCT EXTRACT(YEAR FROM timezone('Europe/Berlin', starts_at))::int AS y"
            f" FROM public_event_v WHERE {base} ORDER BY y DESC"
        ),
        values,
    )
    years = [r.y for r in year_rows.all()]
    chosen = year if year is not None else (years[0] if years else None)
    if chosen is None:
        return PublicArchiveOut(years=years, year=None, items=[], next_cursor=None)
    values["begin"] = day_start(date(chosen, 1, 1))
    values["end"] = day_start(date(chosen + 1, 1, 1))
    condition = f"{base} AND starts_at >= :begin AND starts_at < :end"
    if cursor is not None:
        condition += " AND (starts_at, id) < (:after, :ident)"
        values.update(after=cursor.starts_at, ident=cursor.id)
    sql = text(
        f"SELECT {CARD} FROM public_event_v WHERE {condition}"
        f" ORDER BY starts_at DESC, id DESC LIMIT {limit + 1}"
    )
    rows = (await session.execute(sql, values)).all()
    shown = rows[:limit]
    following = cursors.encode(shown[-1].starts_at, shown[-1].id) if len(rows) > limit else None
    return PublicArchiveOut(
        years=years, year=chosen, items=[cards.to_card(r) for r in shown], next_cursor=following
    )
