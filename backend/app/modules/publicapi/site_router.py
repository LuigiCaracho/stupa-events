"""The site routes of the public API: list and search, detail, today, categories, calendar, archive.

Public, read-only, on the `events_public` connection only; no session, no cookie, no CORS.
Every route answers through `respcache.serve`: a Redis copy for one feed version, `ETag`,
`If-None-Match`, and a rate-limit hit only when the database has to answer. Unknown query
parameters are ignored and do not enter the cache key.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import Field, TypeAdapter
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi import cursor as cursors
from app.modules.publicapi import ratelimit, respcache
from app.modules.publicapi.clock import Now, day_end, day_start, months_between
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.query import cards, memory, pages, search
from app.modules.publicapi.query import facets as facet_queries
from app.modules.publicapi.query.filters import SiteFilters
from app.modules.publicapi.respcache import LONG, SWR, Built
from app.modules.publicapi.site_schemas import (
    PublicArchiveOut,
    PublicCalendarOut,
    PublicCategoryOut,
    PublicEventDetail,
    PublicSearchOut,
    PublicTodayOut,
)
from app.modules.search.words import parse
from app.settings import Settings, get_settings
from app.shared.antiabuse import client_ip, get_rate_limiter
from app.shared.errors import (
    FieldError,
    NotFoundError,
    ProblemDetail,
    ServiceUnavailableError,
    ValidationProblem,
)
from app.shared.ratelimit import RateLimiter

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
SLUG_PARAM = Field(pattern=SLUG.pattern, max_length=80)
Slugs = Annotated[list[Annotated[str, SLUG_PARAM]], Query(max_length=10)]
MONTH_RANGE = 24
DAY_RANGE = Field(ge=date(2000, 1, 1), le=date(2100, 12, 31))
TTL = 60
router = APIRouter(prefix="/public", tags=["public"])
PublicSession = Annotated[AsyncSession, Depends(get_public_session)]
Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {304: {}, 422: _PROBLEM, 429: _PROBLEM, 503: _PROBLEM}
_OUT = {
    PublicSearchOut: TypeAdapter(PublicSearchOut),
    PublicEventDetail: TypeAdapter(PublicEventDetail),
    PublicTodayOut: TypeAdapter(PublicTodayOut),
    PublicCalendarOut: TypeAdapter(PublicCalendarOut),
    PublicArchiveOut: TypeAdapter(PublicArchiveOut),
    list[PublicCategoryOut]: TypeAdapter(list[PublicCategoryOut]),
}


def built(adapter: TypeAdapter[Any], value: object) -> Built:
    """Serialize a wire model to camelCase JSON bytes."""
    return Built(adapter.dump_json(value, by_alias=True), "application/json")


def _miss(request: Request, limiter: RateLimiter, settings: Settings, *, text: bool = False):  # noqa: ANN202
    check = ratelimit.search_limit if text else ratelimit.public_limit

    async def count() -> None:
        await check(limiter, settings, client_ip(request))

    return count


def _problem(field: str, msg: str) -> ValidationProblem:
    return ValidationProblem("Invalid request.", errors=[FieldError(field=field, msg=msg)])


def _timeout(exc: DBAPIError) -> bool:
    return "statement timeout" in str(exc.orig)


@router.api_route(
    "/events", methods=["GET", "HEAD"], response_model=PublicSearchOut, responses=_ERRORS
)
async def list_events(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    q: Annotated[str | None, Query(max_length=300)] = None,
    category: Slugs = [],  # noqa: B006 - FastAPI copies the default
    organization: Slugs = [],  # noqa: B006
    from_: Annotated[date | None, Query(alias="from"), DAY_RANGE] = None,
    to: Annotated[date | None, Query(), DAY_RANGE] = None,
    past: Annotated[bool, Query()] = False,
    building: Annotated[str | None, Query(pattern=r"^[0-9]{1,3}[a-z]?$")] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=300)] = None,
) -> Response:
    """List and search public events with facets on the first page."""
    words = tuple(parse(q))
    if from_ and to and to < from_:
        raise _problem("to", "before from")
    position = search.decode_position(cursor, text=bool(words))
    filters = SiteFilters(
        now=now,
        words=words,
        categories=tuple(category),
        organizations=tuple(organization),
        building=building,
        start=day_start(from_) if from_ else None,
        end=day_end(to) if to else None,
        past=past,
    )

    async def build() -> Built:
        first = not cursor
        try:
            if words:
                out = await memory.search(session, filters, position, limit, first=first)
            else:
                rows, following = await search.page(session, filters, position, limit)
                out = PublicSearchOut(
                    items=[cards.to_card(r) for r in rows],
                    next_cursor=following,
                    total=await facet_queries.total(session, filters) if first else None,
                    facets=await facet_queries.facets(session, filters) if first else None,
                )
        except DBAPIError as exc:
            if not _timeout(exc):
                raise
            raise ServiceUnavailableError(
                "Die Suche ist gerade nicht verfügbar.", code="search_unavailable"
            ) from exc
        return built(_OUT[PublicSearchOut], out)

    key = respcache.cache_key(
        "/events",
        {
            "q": [w.text for w in words],
            "category": sorted(category),
            "organization": sorted(organization),
            "from": from_,
            "to": to,
            "past": past,
            "building": building,
            "limit": limit,
            "cursor": cursor,
        },
    )
    return await respcache.serve(
        request,
        key=key,
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings, text=bool(words)),
    )


@router.api_route(
    "/events/{slug}",
    methods=["GET", "HEAD"],
    response_model=PublicEventDetail,
    responses={**_ERRORS, 404: _PROBLEM},
)
async def event_detail(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    slug: str,
) -> Response:
    """Return one public event; unknown, draft and withdrawn events are all 404."""
    if not SLUG.match(slug):
        raise NotFoundError("not_found")

    async def build() -> Built:
        row = await pages.event_row(session, slug)
        if row is None:
            raise NotFoundError("not_found")
        return built(_OUT[PublicEventDetail], await pages.detail(session, row, now))

    return await respcache.serve(
        request,
        key=respcache.cache_key(f"/events/{slug}", {}),
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )


@router.api_route(
    "/today", methods=["GET", "HEAD"], response_model=PublicTodayOut, responses=_ERRORS
)
async def today(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter, now: Now
) -> Response:
    """Return today at the campus and the next seven days."""

    async def build() -> Built:
        return built(_OUT[PublicTodayOut], await pages.today(session, now))

    return await respcache.serve(
        request,
        key=respcache.cache_key("/today", {}),
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )


@router.api_route(
    "/categories",
    methods=["GET", "HEAD"],
    response_model=list[PublicCategoryOut],
    responses=_ERRORS,
)
async def list_categories(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter, now: Now
) -> Response:
    """Return the active categories with description and upcoming count."""

    async def build() -> Built:
        return built(_OUT[list[PublicCategoryOut]], await pages.categories(session, now))

    return await respcache.serve(
        request,
        key=respcache.cache_key("/categories", {}),
        ttl=60,
        cache_control=LONG,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )


@router.api_route(
    "/calendar", methods=["GET", "HEAD"], response_model=PublicCalendarOut, responses=_ERRORS
)
async def calendar(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    month: Annotated[str, Query(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")],
    category: Annotated[str | None, Query(pattern=SLUG.pattern, max_length=80)] = None,
) -> Response:
    """Return one Berlin month grouped by day (24 months around today at most)."""
    year, number = int(month[:4]), int(month[5:])
    if abs(months_between(now, year, number)) > MONTH_RANGE:
        raise _problem("month", "out of range")

    async def build() -> Built:
        return built(_OUT[PublicCalendarOut], await pages.calendar(session, year, number, category))

    return await respcache.serve(
        request,
        key=respcache.cache_key("/calendar", {"month": month, "category": category}),
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )


@router.api_route(
    "/archive", methods=["GET", "HEAD"], response_model=PublicArchiveOut, responses=_ERRORS
)
async def archive(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    category: Annotated[str | None, Query(pattern=SLUG.pattern, max_length=80)] = None,
    limit: Annotated[int, Query(ge=1, le=48)] = pages.ARCHIVE_DEFAULT_LIMIT,
    cursor: Annotated[str | None, Query(max_length=300)] = None,
) -> Response:
    """Return past events with a poster, one year at a time, newest first."""
    after = cursors.decode(cursor) if cursor else None

    async def build() -> Built:
        out = await pages.archive(session, now, year, category, limit, after)
        return built(_OUT[PublicArchiveOut], out)

    return await respcache.serve(
        request,
        key=respcache.cache_key(
            "/archive", {"year": year, "category": category, "limit": limit, "cursor": cursor}
        ),
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )
