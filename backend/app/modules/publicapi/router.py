"""Public endpoints: the event feed (schema 2) and the derivative images.

These routes run on the `events_public` connection only. They set no cookie, resolve no
session and need no CORS: Astro and WordPress fetch the feed server to server. The feed is
served from the worker snapshot when it is fresh and read live from the view otherwise.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import AwareDatetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.dossier.deps import PublicStorage
from app.modules.dossier.derive import derivative_key
from app.modules.files.storage import StorageError
from app.modules.media.derivatives import parse_derivative_id
from app.modules.publicapi import cursor as cursors
from app.modules.publicapi import serving
from app.modules.publicapi.clock import representable
from app.modules.publicapi.db import get_public_session
from app.modules.publicapi.etag import matches
from app.modules.publicapi.schemas import FeedOut
from app.modules.publicapi.service import FeedQuery, derivative_is_public, feed_json, items_etag
from app.settings import Settings, get_settings
from app.shared.errors import (
    BadRequestError,
    FieldError,
    NotFoundError,
    ProblemDetail,
    ServiceUnavailableError,
    ValidationProblem,
)

NO_CONTROL = r"^[^\x00-\x1f\x7f]*$"
router = APIRouter(prefix="/public", tags=["public"])

FEED_CACHE_CONTROL = "public, max-age=300, stale-while-revalidate=60"
MEDIA_CACHE_CONTROL = "public, max-age=31536000, immutable"
PublicSession = Annotated[AsyncSession, Depends(get_public_session)]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
INVALID_SINCE_HINT = "since must be ISO 8601 with an offset; URL-encode the plus sign as %2B02:00."


def parse_since(raw: str | None) -> datetime | None:
    """Read `since`: ISO 8601 with an offset (`Z` allowed).

    Raises:
        BadRequestError: `invalid_since` for a naive or broken value (an unencoded `+`
            reaches the server as a space, which lands here too).
    """
    if raw is None:
        return None
    try:
        value = datetime.fromisoformat(raw)
        if value.utcoffset() is None or not representable(value):
            raise ValueError("naive or out of range")
    except ValueError as exc:
        raise BadRequestError(INVALID_SINCE_HINT, code="invalid_since") from exc
    return value


def pick_organization(organization: str | None, org: str | None) -> str | None:
    """Return the organization filter; `org` is the old alias and must not disagree."""
    if organization is not None and org is not None and organization != org:
        raise ValidationProblem(
            "organization and org differ.",
            errors=[FieldError(field="org", msg="differs from organization")],
        )
    return organization if organization is not None else org


def check_range(value: datetime | None, field: str) -> None:
    """Reject an instant outside the years 1970 to 2199.

    Raises:
        ValidationProblem: for such a value (the database driver cannot bind it).
    """
    if value is not None and not representable(value):
        raise ValidationProblem(
            "Invalid request.", errors=[FieldError(field=field, msg="outside 1970 to 2199")]
        )


@router.api_route(
    "/feed/events",
    methods=["GET", "HEAD"],
    response_model=FeedOut,
    responses={304: {}, 400: _PROBLEM, 422: _PROBLEM},
)
async def event_feed(
    request: Request,
    session: PublicSession,
    settings: Annotated[Settings, Depends(get_settings)],
    from_: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    to: Annotated[AwareDatetime | None, Query()] = None,
    since: Annotated[str | None, Query(max_length=64)] = None,
    category: Annotated[str | None, Query(max_length=100, pattern=NO_CONTROL)] = None,
    organization: Annotated[str | None, Query(max_length=100, pattern=NO_CONTROL)] = None,
    org: Annotated[str | None, Query(max_length=100, pattern=NO_CONTROL)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
) -> Response:
    """Return the public events by start time with `ETag`, a cursor and a five minute cache."""
    check_range(from_, "from")
    check_range(to, "to")
    query = FeedQuery(
        from_,
        to,
        parse_since(since),
        category,
        pick_organization(organization, org),
        cursors.decode(cursor) if cursor else None,
        limit,
    )
    pool = getattr(request.app.state, "arq_pool", None)
    page = await serving.feed_page(pool, session, query, settings)
    etag = items_etag(page.items, page.next_cursor)
    headers = {"ETag": etag, "Cache-Control": FEED_CACHE_CONTROL}
    if matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=headers)
    body = feed_json(page.items, page.generated_at, page.next_cursor)
    return Response(body, media_type="application/json", headers=headers)


@router.get(
    "/media/{name}",
    response_class=Response,
    responses={
        200: {
            "description": "The image",
            "content": {"image/webp": {"schema": {"type": "string"}}},
        },
        404: _PROBLEM,
        503: _PROBLEM,
    },
)
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
