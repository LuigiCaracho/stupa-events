"""`PUT /events/{id}/facts`: the profile fields of a dossier (capacity, age limit, budget ...)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from app.deps import DbSession, Principal, require_any_scope
from app.modules.events.conflict import require_if_match, set_etag, with_current
from app.modules.events.facts_service import put_facts
from app.modules.events.presenter import present
from app.modules.events.schemas import EventOut
from app.shared.errors import ProblemDetail

router = APIRouter(tags=["events"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422, 428)}
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


@router.put("/events/{event_id}/facts", response_model=EventOut, responses=_ERRORS)
async def put_event_facts(
    db: DbSession,
    principal: Editor,
    event_id: UUID,
    body: dict[str, Any],
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Replace the facts; the keys must belong to the profile of the main category."""
    async with with_current(db, principal):
        event = await put_facts(db, principal, event_id, body, require_if_match(if_match))
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    set_etag(response, out.rev)
    return out
