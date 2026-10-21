"""Follow-up routes: the outcome of an event and the verification of its howto."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response

from app.deps import DbSession, Principal, require_any_scope
from app.modules.events.conflict import require_if_match, set_etag, with_current
from app.modules.events.presenter import present
from app.modules.events.schemas import EventOut
from app.modules.followup import howto, outcome
from app.modules.followup.schemas import OutcomeIn
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/events/{event_id}", tags=["followup"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422, 428)}
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]
Submitter = Annotated[Principal, Depends(require_any_scope("event.submit"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


@router.put("/outcome", response_model=EventOut, responses=_ERRORS)
async def put_outcome(
    db: DbSession,
    principal: Editor,
    event_id: UUID,
    body: OutcomeIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Replace the outcome (attendance, costs, revenue, notes or the waiver) of a dossier."""
    async with with_current(db, principal):
        event = await outcome.put_outcome(db, principal, event_id, body, require_if_match(if_match))
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    set_etag(response, out.rev)
    return out


@router.post("/actions/verify-howto", response_model=EventOut, responses=_ERRORS)
async def verify_howto(
    db: DbSession, principal: Submitter, event_id: UUID, response: Response
) -> EventOut:
    """Mark the howto verified; after the archive this also dates the format."""
    event = await howto.verify(db, principal, event_id)
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    set_etag(response, out.rev)
    return out


@router.delete("/actions/verify-howto", response_model=EventOut, responses=_ERRORS)
async def unverify_howto(
    db: DbSession, principal: Submitter, event_id: UUID, response: Response
) -> EventOut:
    """Take the verification away again, as long as the dossier is not archived."""
    event = await howto.unverify(db, principal, event_id)
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    set_etag(response, out.rev)
    return out
