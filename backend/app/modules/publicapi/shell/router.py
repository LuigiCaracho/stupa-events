"""The HTML shell routes: `/`, `/suche`, `/kalender`, `/rueckblick`, `/e/{slug}`, `/k/{slug}`,
`/sitemap.xml` and `/robots.txt`.

Public, cookie-free, on the `events_public` connection. Each page is the built SPA index with
title, Open Graph, calendar links and JSON-LD filled in (see `page.py`). An unknown event or
category gets the SPA markup with status 404 and `noindex`. The query string never changes a
page, so it does not enter the cache key or any log of ours.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.events.postcommit import request_rebuild
from app.modules.publicapi import cache, ratelimit, respcache
from app.modules.publicapi.clock import Now
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.etag import matches
from app.modules.publicapi.query import cards, pages, search
from app.modules.publicapi.query.filters import SiteFilters
from app.modules.publicapi.respcache import SWR, Built
from app.modules.publicapi.shell import meta, sitemap
from app.modules.publicapi.shell.page import HTML_HEADERS, load_index, render
from app.settings import Settings, get_settings
from app.shared.antiabuse import client_ip, get_rate_limiter
from app.shared.errors import ProblemDetail
from app.shared.ratelimit import RateLimiter

SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
HTML = "text/html; charset=utf-8"
HOME_ITEMS, CATEGORY_ITEMS = 20, 20
router = APIRouter(tags=["shell"])
PublicSession = Annotated[AsyncSession, Depends(get_public_session)]
Limiter = Annotated[RateLimiter, Depends(get_rate_limiter)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
_PAGE = {"content": {"text/html": {"schema": {"type": "string"}}}}
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_OWN_404 = {"x-error-contract": "html"}
_HTML: dict[int | str, dict[str, Any]] = {
    200: _PAGE,
    304: {},
    404: _PAGE,
    429: _PROBLEM,
    503: _PROBLEM,
}


async def _answer(
    request: Request,
    settings: Settings,
    limiter: Limiter,
    path: str,
    describe: Callable[[], Awaitable[meta.Page]],
) -> Response:
    async def build() -> Built:
        page = await describe()
        status = 404 if page.noindex else 200
        return Built(
            render(load_index(settings.spa_index_path), page, settings.public_base_url).encode(),
            HTML,
            status,
        )

    async def count() -> None:
        await ratelimit.public_limit(limiter, settings, client_ip(request))

    return await respcache.serve(
        request,
        key=respcache.cache_key(path, {}),
        ttl=60,
        cache_control=SWR,
        build=build,
        on_miss=count,
        headers=HTML_HEADERS,
    )


async def _fixed(
    request: Request, session: AsyncSession, settings: Settings, limiter: RateLimiter, path: str
) -> Response:
    base = settings.public_base_url.rstrip("/")

    async def describe() -> meta.Page:
        return meta.fixed_page(path, base)

    return await _answer(request, settings, limiter, path, describe)


@router.api_route("/", methods=["GET", "HEAD"], response_class=Response, responses=_HTML)
async def home(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter, now: Now
) -> Response:
    """Return the start page; its noscript list names today's and the next events."""
    base = settings.public_base_url.rstrip("/")

    async def describe() -> meta.Page:
        rows, _ = await search.page(session, SiteFilters(now=now), search.Position(), HOME_ITEMS)
        return meta.home_page(base, [cards.to_card(r) for r in rows])

    return await _answer(request, settings, limiter, "/", describe)


@router.api_route("/suche", methods=["GET", "HEAD"], response_class=Response, responses=_HTML)
async def search_page(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter
) -> Response:
    """Return the search page (the query string changes nothing)."""
    return await _fixed(request, session, settings, limiter, "/suche")


@router.api_route("/kalender", methods=["GET", "HEAD"], response_class=Response, responses=_HTML)
async def calendar_page(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter
) -> Response:
    """Return the calendar page."""
    return await _fixed(request, session, settings, limiter, "/kalender")


@router.api_route("/rueckblick", methods=["GET", "HEAD"], response_class=Response, responses=_HTML)
async def archive_page(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter
) -> Response:
    """Return the look-back page."""
    return await _fixed(request, session, settings, limiter, "/rueckblick")


@router.api_route(
    "/e/{slug}",
    methods=["GET", "HEAD"],
    response_class=Response,
    responses=_HTML,
    openapi_extra=_OWN_404,
)
async def event_page(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter, slug: str
) -> Response:
    """Return the event page for link previews and search engines."""
    base = settings.public_base_url.rstrip("/")

    async def describe() -> meta.Page:
        row = await pages.event_row(session, slug) if SLUG.match(slug) else None
        return meta.event_page(row, base) if row else meta.not_found_page(f"/e/{slug}", base)

    return await _answer(request, settings, limiter, f"/e/{slug}", describe)


@router.api_route(
    "/k/{slug}",
    methods=["GET", "HEAD"],
    response_class=Response,
    responses=_HTML,
    openapi_extra=_OWN_404,
)
async def category_page(
    request: Request,
    session: PublicSession,
    settings: SettingsDep,
    limiter: Limiter,
    now: Now,
    slug: str,
) -> Response:
    """Return the category page; an inactive or unknown category is a 404."""
    base = settings.public_base_url.rstrip("/")

    async def describe() -> meta.Page:
        found = None
        if SLUG.match(slug):
            found = (
                await session.execute(
                    text(
                        "SELECT name, description FROM public_category_v WHERE slug = :s AND active"
                    ),
                    {"s": slug},
                )
            ).first()
        if found is None:
            return meta.not_found_page(f"/k/{slug}", base)
        filters = SiteFilters(now=now, categories=(slug,))
        rows, _ = await search.page(session, filters, search.Position(), CATEGORY_ITEMS)
        upcoming = [cards.to_card(r) for r in rows]
        return meta.category_page(slug, found.name, found.description, base, upcoming)

    return await _answer(request, settings, limiter, f"/k/{slug}", describe)


@router.api_route(
    "/sitemap.xml",
    methods=["GET", "HEAD"],
    response_class=Response,
    responses={
        200: {"content": {"application/xml": {"schema": {"type": "string"}}}},
        304: {},
        429: _PROBLEM,
    },
)
async def sitemap_xml(
    request: Request, session: PublicSession, settings: SettingsDep, limiter: Limiter, now: Now
) -> Response:
    """Return the sitemap from the worker snapshot, or build it live from the view."""
    redis = getattr(request.app.state, "arq_pool", None)
    snap = await cache.load(
        redis, sitemap.SNAPSHOT, max_age_seconds=settings.public_snapshot_max_age_seconds
    )
    if snap is not None:
        body, etag = snap.body, snap.etag
    else:
        await ratelimit.public_limit(limiter, settings, client_ip(request))
        events, categories = await sitemap.read(session, now)
        body = sitemap.build(settings.public_base_url, events, categories)
        etag = cache.etag_of(body)
        if redis is not None:
            await request_rebuild(redis)
    headers = {"ETag": etag, "Cache-Control": "public, max-age=3600"}
    if matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type=sitemap.SITEMAP_TYPE, headers=headers)


@router.api_route(
    "/robots.txt",
    methods=["GET", "HEAD"],
    response_class=Response,
    responses={200: {"content": {"text/plain": {"schema": {"type": "string"}}}}},
)
async def robots_txt(session: PublicSession, settings: SettingsDep) -> Response:
    """Return `robots.txt`."""
    body = sitemap.robots(settings.public_base_url)
    return Response(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Cache-Control": "public, max-age=3600"},
    )
