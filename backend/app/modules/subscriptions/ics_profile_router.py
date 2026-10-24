"""Profile calendar: `GET /ics/p/{token}.ics`, the union of the profile's category calendars.

The token is the credential: 256 bits, looked up by its SHA-256 digest. Unknown, rotated and
revoked tokens give the same 404 after the same database access, whatever the shape of the
token. The body is merged from the worker's category snapshots (never computed from the
database on the hot path), so a profile costs a few Redis reads. The answer is `private`,
`no-referrer` and `noindex`; the route never logs the path or the token, and each miss counts
against a per-IP limit.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.publicapi import cache, ratelimit, serving
from app.modules.publicapi.etag import matches
from app.modules.subscriptions import limits
from app.modules.subscriptions.db import get_subs_session
from app.modules.subscriptions.ics_merge import merge
from app.modules.subscriptions.problems import calendar_not_found_response
from app.modules.subscriptions.tokens import hash_token
from app.shared.antiabuse import RateLimiterDep, SettingsDep, client_ip
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/ics", tags=["ics"])

CACHE_CONTROL = "private, max-age=900"
DISPOSITION = 'inline; filename="stupa-events.ics"'
MISS_LIMIT_PER_HOUR = 30
SubsSession = Annotated[AsyncSession, Depends(get_subs_session)]
_FIND = text("SELECT id, categories FROM subscription_profile WHERE ics_token_hash = :h")
_TOUCH = text(
    "UPDATE subscription_profile SET last_fetched_on = current_date "
    "WHERE id = :id AND last_fetched_on IS DISTINCT FROM current_date"
)
_CALENDAR: dict[int | str, dict[str, Any]] = {
    200: {
        "description": "The calendar",
        "content": {"text/calendar": {"schema": {"type": "string"}}},
    },
    304: {"description": "Not modified"},
    404: {"model": ProblemDetail},
    429: {"model": ProblemDetail},
}


async def _bodies(
    request: Request, session: AsyncSession, settings: SettingsDep, slugs: list[str]
) -> list[bytes]:
    pool = getattr(request.app.state, "arq_pool", None)
    documents = [
        await serving.ics_document(pool, session, cache.ics_name(slug), slug, settings)
        for slug in slugs
    ]
    return [d.body for d in documents if d is not None]


@router.api_route(
    "/p/{token}.ics", methods=["GET", "HEAD"], response_class=Response, responses=_CALENDAR
)
async def profile_calendar(
    request: Request,
    token: str,
    session: SubsSession,
    settings: SettingsDep,
    limiter: RateLimiterDep,
) -> Response:
    """Return the calendar of one profile (404 for every token that is not a live one)."""
    ip = client_ip(request)
    await ratelimit.public_limit(limiter, settings, ip)
    row = (await session.execute(_FIND, {"h": hash_token(token)})).first()
    if row is None:
        await limits.hit_ip(limiter, "ics-p-miss", ip, limit=MISS_LIMIT_PER_HOUR)
        return calendar_not_found_response()
    body = merge(await _bodies(request, session, settings, list(row.categories)))
    await session.execute(_TOUCH, {"id": row.id})
    await session.commit()
    etag = cache.etag_of(body)
    headers = {
        "ETag": etag,
        "Cache-Control": CACHE_CONTROL,
        "Content-Disposition": DISPOSITION,
        "Referrer-Policy": "no-referrer",
        "X-Robots-Tag": "noindex",
    }
    if matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(body, media_type=serving.ICS_TYPE, headers=headers)
