"""`POST /events/{id}/actions/confirm-location`: a publisher confirms the free venue text."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response

from app.deps import DbSession, Principal, require_any_scope
from app.modules.auth.schemas import CamelModel
from app.modules.events.conflict import parse_if_match
from app.modules.events.location import confirm_location
from app.modules.events.respond import respond
from app.modules.events.schemas import EventOut
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/events/{event_id}/actions", tags=["actions"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422)}
Publisher = Annotated[Principal, Depends(require_any_scope("event.publish"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


class ConfirmLocationIn(CamelModel):
    """Body of `confirm-location`: how precise the public place is. `hidden` is not an answer."""

    precision: Literal["exact", "building"]


@router.post("/confirm-location", response_model=EventOut, responses=_ERRORS)
async def confirm_location_route(
    request: Request,
    db: DbSession,
    principal: Publisher,
    event_id: UUID,
    body: ConfirmLocationIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Confirm that the free venue text may be shown to the public. No private address."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: confirm_location(
            db, principal, event_id, body.precision, expected_rev=parse_if_match(if_match)
        ),
    )
