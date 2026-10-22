"""Calendar subscriptions: `GET /ics/all.ics` and `GET /ics/k/<category-slug>.ics`.

Public, read-only, on the `events_public` connection (E14). No session, no cookie, no CORS,
no query parameters (they are ignored). The bytes come from the worker snapshot when it is
fresh and from the view otherwise. A personal profile calendar with a token is stage B and
not built here.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi import cache, ratelimit, respcache, serving
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.etag import matches
from app.modules.publicapi.ics.rows import ics_row
from app.modules.publicapi.ics.writer import build_calendar
from app.modules.publicapi.query.pages import event_row
from app.settings import Settings, get_settings
from app.shared.antiabuse import client_ip, get_rate_limiter
from app.shared.errors import NotFoundError, ProblemDetail
from app.shared.ratelimit import RateLimiter

router = APIRouter(prefix="/ics", tags=["ics"])

ICS_CACHE_CONTROL = "public, max-age=3600"
DISPOSITION = 'inline; filename="stupa-events.ics"'
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
EVENT_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
PublicSession = Annotated[AsyncSession, Depends(get_public_session)]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_CALENDAR: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "The calendar",
        "content": {"text/calendar": {"schema": {"type": "string"}}},
    },
    304: {"description": "Not modified"},
    404: _PROBLEM,
}


async def _respond(
    request: Request,
    session: AsyncSession,
    settings: Settings,
    name: str,
    category: str | None,
) -> Response:
    pool = getattr(request.app.state, "arq_pool", None)
    document = await serving.ics_document(pool, session, name, category, settings)
    if document is None:
        raise NotFoundError("calendar not found")
    headers = {
        "ETag": document.etag,
        "Cache-Control": ICS_CACHE_CONTROL,
        "Content-Disposition": DISPOSITION,
    }
    if matches(request.headers.get("if-none-match"), document.etag):
        return Response(status_code=304, headers=headers)
    return Response(document.body, media_type=serving.ICS_TYPE, headers=headers)


@router.api_route("/all.ics", methods=["GET", "HEAD"], response_class=Response, responses=_CALENDAR)
async def all_events(
    request: Request, session: PublicSession, settings: Annotated[Settings, Depends(get_settings)]
) -> Response:
    """Return the calendar of every public event."""
    return await _respond(request, session, settings, cache.ICS_ALL, None)


@router.api_route(
    "/k/{slug}.ics", methods=["GET", "HEAD"], response_class=Response, responses=_CALENDAR
)
async def category_events(
    request: Request,
    session: PublicSession,
    settings: Annotated[Settings, Depends(get_settings)],
    slug: str,
) -> Response:
    """Return the calendar of one category and its child categories (404 for an unknown slug)."""
    if not SLUG.match(slug):
        raise NotFoundError("calendar not found")
    return await _respond(request, session, settings, cache.ics_name(slug), slug)


@router.api_route(
    "/e/{slug}.ics",
    methods=["GET", "HEAD"],
    response_class=Response,
    responses={**_CALENDAR, 429: _PROBLEM},
)
async def one_event(
    request: Request,
    session: PublicSession,
    settings: Annotated[Settings, Depends(get_settings)],
    limiter: Annotated[RateLimiter, Depends(get_rate_limiter)],
    slug: str,
) -> Response:
    """Return the calendar file of one event (past ones too), as a download."""
    if not EVENT_SLUG.match(slug):
        raise NotFoundError("calendar not found")

    async def build() -> respcache.Built:
        row = await event_row(session, slug)
        if row is None:
            raise NotFoundError("calendar not found")
        body = build_calendar(
            [ics_row(row)],
            base_url=settings.public_base_url,
            uid_domain=settings.ics_uid_domain,
            name=row.title,
        )
        return respcache.Built(body, serving.ICS_TYPE)

    async def count() -> None:
        await ratelimit.public_limit(limiter, settings, client_ip(request))

    return await respcache.serve(
        request,
        key=respcache.cache_key(f"/ics/e/{slug}", {}),
        ttl=300,
        cache_control=respcache.LONG,
        build=build,
        on_miss=count,
        headers={"Content-Disposition": f'attachment; filename="{slug}.ics"'},
    )
