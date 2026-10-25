"""The map routes of the public API: events as points, campus buildings and their events.

Same mechanics as `site_router`: public, read-only, on the `events_public` connection, a Redis
copy per feed version through `respcache.serve`, a rate-limit hit only on a miss. Coordinates
come rounded from the view; this module never reads a venue row.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi import ratelimit, respcache
from app.modules.publicapi.clock import Now, berlin_date, day_end, day_start
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.map_schemas import PublicCampusCollection, PublicMapCollection
from app.modules.publicapi.query import cards, maps, search
from app.modules.publicapi.query import facets as facet_queries
from app.modules.publicapi.query.filters import SiteFilters
from app.modules.publicapi.respcache import SWR, Built
from app.modules.publicapi.site_router import DAY_RANGE, TTL, Slugs, built
from app.modules.publicapi.site_schemas import PublicSearchOut
from app.settings import Settings, get_settings
from app.shared.antiabuse import client_ip, get_rate_limiter
from app.shared.errors import FieldError, NotFoundError, ProblemDetail, ValidationProblem
from app.shared.ratelimit import RateLimiter

BUILDING = r"^[0-9]{1,3}[a-z]?$"
MAP_LIMIT = 1000
router = APIRouter(prefix="/public", tags=["public"])
PublicSession = Annotated[AsyncSession, Depends(get_public_session)]
Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {304: {}, 422: _PROBLEM, 429: _PROBLEM, 503: _PROBLEM}
_OUT = {
    PublicMapCollection: TypeAdapter(PublicMapCollection),
    PublicCampusCollection: TypeAdapter(PublicCampusCollection),
    PublicSearchOut: TypeAdapter(PublicSearchOut),
}


def _miss(request: Request, limiter: RateLimiter, settings: Settings):  # noqa: ANN202
    async def count() -> None:
        await ratelimit.public_limit(limiter, settings, client_ip(request))

    return count


def _problem(field: str, msg: str) -> ValidationProblem:
    return ValidationProblem("Invalid request.", errors=[FieldError(field=field, msg=msg)])


def parse_bbox(raw: str | None) -> maps.BBox | None:
    """Read `minLon,minLat,maxLon,maxLat`; anything else is a 422."""
    if raw is None:
        return None
    try:
        west, south, east, north = (float(part) for part in raw.split(","))
    except ValueError:
        raise _problem("bbox", "expected four numbers") from None
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise _problem("bbox", "out of range")
    return west, south, east, north


def _days(from_: date | None, to: date | None, now: Any) -> tuple[Any, Any]:
    if from_ and to and to < from_:
        raise _problem("to", "before from")
    today = berlin_date(now)
    return day_start(from_ or today), day_end(to or from_ or today)


@router.api_route(
    "/map/events", methods=["GET", "HEAD"], response_model=PublicMapCollection, responses=_ERRORS
)
async def map_events(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    category: Slugs = [],  # noqa: B006 - FastAPI copies the default
    organization: Slugs = [],  # noqa: B006
    from_: Annotated[date | None, Query(alias="from"), DAY_RANGE] = None,
    to: Annotated[date | None, Query(), DAY_RANGE] = None,
    past: Annotated[bool, Query()] = False,
    bbox: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=2000)] = MAP_LIMIT,
) -> Response:
    """Return the events with a public coordinate as GeoJSON points."""
    if from_ and to and to < from_:
        raise _problem("to", "before from")
    box = parse_bbox(bbox)
    filters = SiteFilters(
        now=now,
        categories=tuple(category),
        organizations=tuple(organization),
        start=day_start(from_) if from_ else None,
        end=day_end(to) if to else None,
        past=past,
    )

    async def build() -> Built:
        return built(
            _OUT[PublicMapCollection], await maps.events(session, filters, box, limit, now)
        )

    key = respcache.cache_key(
        "/map/events",
        {
            "category": sorted(category),
            "organization": sorted(organization),
            "from": from_,
            "to": to,
            "past": past,
            "bbox": box,
            "limit": limit,
        },
    )
    return await respcache.serve(
        request,
        key=key,
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )


@router.api_route(
    "/campus/buildings",
    methods=["GET", "HEAD"],
    response_model=PublicCampusCollection,
    responses=_ERRORS,
)
async def campus_buildings(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    from_: Annotated[date | None, Query(alias="from"), DAY_RANGE] = None,
    to: Annotated[date | None, Query(), DAY_RANGE] = None,
) -> Response:
    """Return the building polygons with the event count of the range (today by default)."""
    start, end = _days(from_, to, now)
    filters = SiteFilters(now=now, start=start, end=end)

    async def build() -> Built:
        return built(_OUT[PublicCampusCollection], await maps.campus(session, filters, now))

    return await respcache.serve(
        request,
        key=respcache.cache_key("/campus/buildings", {"from": start, "to": end}),
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )


@router.api_route(
    "/campus/events",
    methods=["GET", "HEAD"],
    response_model=PublicSearchOut,
    responses={**_ERRORS, 404: _PROBLEM},
)
async def campus_events(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    building: Annotated[str, Query(pattern=BUILDING)],
    from_: Annotated[date | None, Query(alias="from"), DAY_RANGE] = None,
    to: Annotated[date | None, Query(), DAY_RANGE] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    cursor: Annotated[str | None, Query(max_length=300)] = None,
) -> Response:
    """Return the events of one campus building in the range (today by default)."""
    start, end = _days(from_, to, now)
    position = search.decode_position(cursor, text=False)
    filters = SiteFilters(now=now, building=building, start=start, end=end)

    async def build() -> Built:
        known = await session.scalar(
            text("SELECT 1 FROM public_campus_building_v WHERE number = :n"), {"n": building}
        )
        if known is None:
            raise NotFoundError("not_found")
        rows, following = await search.page(session, filters, position, limit)
        out = PublicSearchOut(
            items=[cards.to_card(r) for r in rows],
            next_cursor=following,
            total=None if cursor else await facet_queries.total(session, filters),
            facets=None,
        )
        return built(_OUT[PublicSearchOut], out)

    return await respcache.serve(
        request,
        key=respcache.cache_key(
            "/campus/events",
            {"building": building, "from": start, "to": end, "limit": limit, "cursor": cursor},
        ),
        ttl=TTL,
        cache_control=SWR,
        build=build,
        on_miss=_miss(request, limiter, settings),
    )
