"""Public endpoints: the event feed (schema 2) and the derivative images.

These routes run on the `events_public` connection only. They set no cookie, resolve no
session and need no CORS: Astro and WordPress fetch the feed server to server.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dossier.deps import PublicStorage
from app.modules.dossier.derive import derivative_key
from app.modules.files.storage import StorageError
from app.modules.media.derivatives import parse_derivative_id
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.schemas import FeedOut
from app.modules.publicapi.service import (
    FeedQuery,
    derivative_is_public,
    feed_items,
    feed_json,
    items_etag,
)
from app.settings import get_settings
from app.shared.errors import NotFoundError, ProblemDetail, ServiceUnavailableError
from app.shared.timeutil import utcnow

router = APIRouter(prefix="/public", tags=["public"])

FEED_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"
MEDIA_CACHE_CONTROL = "public, max-age=31536000, immutable"
PublicSession = Annotated[AsyncSession, Depends(get_public_session)]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}


def _matches(header: str | None, etag: str) -> bool:
    if header is None:
        return False
    candidates = {part.strip().removeprefix("W/") for part in header.split(",")}
    return "*" in candidates or etag in candidates


@router.get("/feed/events", response_model=FeedOut, responses={304: {}, 422: _PROBLEM})
async def event_feed(
    request: Request,
    session: PublicSession,
    from_: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    to: Annotated[AwareDatetime | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    org: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> Response:
    """Return the public events by start time with `ETag` and a five minute cache."""
    base_url = get_settings().public_base_url.rstrip("/")
    items = await feed_items(session, FeedQuery(from_, to, category, org, limit), base_url)
    etag = items_etag(items)
    headers = {"ETag": etag, "Cache-Control": FEED_CACHE_CONTROL}
    if _matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    return Response(feed_json(items, utcnow()), media_type="application/json", headers=headers)


@router.get("/media/{name}", responses={404: _PROBLEM, 503: _PROBLEM})
async def media(session: PublicSession, storage: PublicStorage, name: str) -> Response:
    """Stream one WebP derivative of a public event's poster, cached for a year."""
    derivative = name.removesuffix(".webp")
    parsed = parse_derivative_id(derivative) if name.endswith(".webp") else None
    if parsed is None or not await derivative_is_public(session, *parsed, derivative):
        raise NotFoundError("media not found")
    if storage is None:
        raise ServiceUnavailableError("Object storage unavailable.")
    try:
        body = await storage.get(derivative_key(derivative))
    except StorageError as exc:
        raise ServiceUnavailableError("Media temporarily unavailable.") from exc
    return Response(body, media_type="image/webp", headers={"Cache-Control": MEDIA_CACHE_CONTROL})
