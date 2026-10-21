"""Autosave endpoints of a dossier: `PUT`, `GET` and `DELETE /events/{id}/draft` (E21)."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.routing import APIRoute

from app.deps import DbSession, Principal, require_any_scope
from app.modules.auth.schemas import CamelModel
from app.modules.events import drafts
from app.modules.events.conflict import parse_if_match, with_current
from app.modules.events.schemas import DraftFields
from app.modules.events.service import EventService
from app.shared.errors import PayloadTooLargeError, PreconditionRequiredError, ProblemDetail

MAX_DRAFT_BYTES = 64 * 1024
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    413: _PROBLEM,
    422: _PROBLEM,
    428: _PROBLEM,
}
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]


class DraftIn(CamelModel):
    """Body of `PUT /draft`: the unsaved fields."""

    fields: DraftFields


class DraftOut(CamelModel):
    """The stored draft."""

    base_rev: int
    fields: dict[str, Any]
    updated_at: datetime


class CappedBodyRoute(APIRoute):
    """Route that reads the body as a stream and stops with 413 above 64 KiB."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        """Wrap the handler: read at most `MAX_DRAFT_BYTES`, then hand the body on."""
        handler = super().get_route_handler()

        async def capped(request: Request) -> Response:
            declared = request.headers.get("content-length")
            if declared and declared.isdigit() and int(declared) > MAX_DRAFT_BYTES:
                raise PayloadTooLargeError("The draft exceeds 64 KiB.")
            body = bytearray()
            async for chunk in request.stream():
                body += chunk
                if len(body) > MAX_DRAFT_BYTES:
                    raise PayloadTooLargeError("The draft exceeds 64 KiB.")
            request._body = bytes(body)  # noqa: SLF001
            return await handler(request)

        return capped


router = APIRouter(prefix="/events", tags=["drafts"], route_class=CappedBodyRoute)


def _out(row: Any) -> DraftOut:
    return DraftOut(base_rev=row.base_rev, fields=row.fields, updated_at=row.updated_at)


@router.put(
    "/{event_id}/draft",
    response_model=DraftOut,
    responses=_ERRORS,
)
async def put_draft(
    db: DbSession,
    principal: Editor,
    event_id: UUID,
    body: DraftIn,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> DraftOut:
    """Store the caller's draft; no revision, no `public_seq`, no audit entry."""
    expected = parse_if_match(if_match)
    if expected is None:
        raise PreconditionRequiredError("An If-Match header is required.")
    service = EventService(db)
    async with with_current(db, principal):
        row = await drafts.put_draft(db, service, principal, event_id, body.fields, expected)
    out = _out(row)
    await db.commit()
    return out


@router.get(
    "/{event_id}/draft",
    response_model=DraftOut,
    responses={**_ERRORS, 204: {"description": "No draft"}},
)
async def get_draft(db: DbSession, principal: Editor, event_id: UUID) -> DraftOut | Response:
    """Return the caller's own draft, or 204."""
    row = await drafts.get_draft(db, principal, event_id)
    return _out(row) if row is not None else Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{event_id}/draft", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def delete_draft(db: DbSession, principal: Editor, event_id: UUID) -> Response:
    """Discard the caller's own draft."""
    await drafts.delete_draft(db, principal, event_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
