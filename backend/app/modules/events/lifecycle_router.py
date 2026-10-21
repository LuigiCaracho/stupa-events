"""Lifecycle routes: publish, unpublish, archive, restore, cancel, postpone, reinstate, revert.

The route gate asks for the right somewhere (403 otherwise); the service then loads the
dossier (404 without a read right) and decides on the organization of the dossier. Every
route needs `If-Match` and answers the changed `EventOut` with its new ETag.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response

from app.deps import DbSession, Principal, SettingsDep, require_any_scope
from app.modules.events import lifecycle, public_status, revert
from app.modules.events.conflict import require_if_match
from app.modules.events.respond import respond
from app.modules.events.schemas import (
    CancelIn,
    EmptyIn,
    EventOut,
    PostponeIn,
    ReinstateIn,
    RevertIn,
)
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/events/{event_id}", tags=["lifecycle"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422, 428)}
Publisher = Annotated[Principal, Depends(require_any_scope("event.publish"))]
Canceller = Annotated[Principal, Depends(require_any_scope("event.cancel"))]
Restorer = Annotated[Principal, Depends(require_any_scope("event.restore"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


@router.post("/publish", response_model=EventOut, responses=_ERRORS)
async def publish(
    request: Request,
    db: DbSession,
    settings: SettingsDep,
    principal: Publisher,
    event_id: UUID,
    response: Response,
    body: EmptyIn | None = None,
    if_match: IfMatch = None,
) -> EventOut:
    """Publish a draft: the dossier gets its slug and enters the public feed."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: lifecycle.publish(
            db,
            principal,
            event_id,
            expected_rev=require_if_match(if_match),
            requires_editor=settings.publish_requires_editor,
        ),
    )


@router.post("/unpublish", response_model=EventOut, responses=_ERRORS)
async def unpublish(
    request: Request,
    db: DbSession,
    principal: Publisher,
    event_id: UUID,
    response: Response,
    body: EmptyIn | None = None,
    if_match: IfMatch = None,
) -> EventOut:
    """Take a published dossier back to draft."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: lifecycle.unpublish(
            db, principal, event_id, expected_rev=require_if_match(if_match)
        ),
    )


@router.post("/archive", response_model=EventOut, responses=_ERRORS)
async def archive(
    request: Request,
    db: DbSession,
    principal: Publisher,
    event_id: UUID,
    response: Response,
    body: EmptyIn | None = None,
    if_match: IfMatch = None,
) -> EventOut:
    """Archive a draft or a published dossier."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: lifecycle.archive(db, principal, event_id, expected_rev=require_if_match(if_match)),
    )


@router.post("/restore", response_model=EventOut, responses=_ERRORS)
async def restore(
    request: Request,
    db: DbSession,
    principal: Restorer,
    event_id: UUID,
    response: Response,
    body: EmptyIn | None = None,
    if_match: IfMatch = None,
) -> EventOut:
    """Bring an archived dossier back as a draft (editorial team)."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: lifecycle.restore(db, principal, event_id, expected_rev=require_if_match(if_match)),
    )


@router.post("/cancel", response_model=EventOut, responses=_ERRORS)
async def cancel(
    request: Request,
    db: DbSession,
    principal: Canceller,
    event_id: UUID,
    body: CancelIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Cancel a published event; the dossier stays published, the public status changes."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: public_status.cancel(
            db,
            principal,
            event_id,
            reason=body.reason,
            public_reason_code=body.public_reason_code,
            public_reason_text=body.public_reason_text,
            expected_rev=require_if_match(if_match),
        ),
    )


@router.post("/postpone", response_model=EventOut, responses=_ERRORS)
async def postpone(
    request: Request,
    db: DbSession,
    principal: Canceller,
    event_id: UUID,
    body: PostponeIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Postpone a published event, optionally with the new date."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: public_status.postpone(
            db,
            principal,
            event_id,
            reason=body.reason,
            public_reason_code=body.public_reason_code,
            public_reason_text=body.public_reason_text,
            new_starts_at=body.new_starts_at,
            new_ends_at=body.new_ends_at,
            expected_rev=require_if_match(if_match),
        ),
    )


@router.post("/reinstate", response_model=EventOut, responses=_ERRORS)
async def reinstate(
    request: Request,
    db: DbSession,
    principal: Canceller,
    event_id: UUID,
    body: ReinstateIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Take back a cancellation or postponement."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: public_status.reinstate(
            db,
            principal,
            event_id,
            reason=body.reason,
            expected_rev=require_if_match(if_match),
        ),
    )


@router.post("/actions/revert-revision", response_model=EventOut, responses=_ERRORS)
async def revert_revision(
    request: Request,
    db: DbSession,
    principal: Annotated[Principal, Depends(require_any_scope("event.edit"))],
    event_id: UUID,
    body: RevertIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Write a new revision with the content of an earlier one."""
    return await respond(
        request,
        db,
        principal,
        response,
        lambda: revert.revert_revision(
            db,
            principal,
            event_id,
            rev=body.rev,
            note=body.note,
            expected_rev=require_if_match(if_match),
        ),
    )
