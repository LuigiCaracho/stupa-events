"""Dossier actions beside the states: `POST /events/{id}/actions/{name}` (contract 5.4)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.events.conflict import parse_if_match, require_if_match, set_etag, with_current
from app.modules.events.presenter import present
from app.modules.events.schemas import (
    AssignOrganizationIn,
    CancelIn,
    EmptyIn,
    EventOut,
    ImageExceptionIn,
    PostponeIn,
    ReinstateIn,
    RevertIn,
)
from app.modules.notifications.service import dispatch_mails
from app.modules.pipeline import actions_service, assign, marks, revert
from app.modules.pipeline.actions import run_actions
from app.modules.pipeline.exception import grant_image_exception
from app.modules.pipeline.service import Fired
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/events/{event_id}/actions", tags=["actions"])
alias_router = APIRouter(prefix="/events", tags=["actions"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    422: _PROBLEM,
    428: _PROBLEM,
}
IfMatch = Annotated[str | None, Header(alias="If-Match")]
Canceller = Annotated[Principal, Depends(require_any_scope("event.cancel"))]
Approver = Annotated[Principal, Depends(require_any_scope("event.approve"))]
Granter = Annotated[Principal, Depends(require_principal("event.image_exception"))]
Assigner = Annotated[Principal, Depends(require_principal("event.assign_org"))]
CriticalEditor = Annotated[Principal, Depends(require_any_scope("event.edit_critical_live"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]


async def _run(
    request: Request,
    db: DbSession,
    principal: Principal,
    response: Response,
    work: Callable[[], Awaitable[Fired]],
) -> EventOut:
    async with with_current(db, principal):
        fired = await work()
    out = (await present(db, principal, [fired.event]))[0]
    out.checklist_recomputed = db.info.pop("checklist_recomputed", None)
    await db.commit()
    set_etag(response, out.rev)
    pool = getattr(request.app.state, "arq_pool", None)
    await run_actions(pool, fired.actions, fired.committed)
    await dispatch_mails(pool, fired.mails)
    return out


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
    """Cancel a live event; the dossier stays `live`, the public status becomes `cancelled`."""
    return await _run(
        request,
        db,
        principal,
        response,
        lambda: actions_service.cancel(
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
    """Postpone a live event, optionally with the new date."""
    return await _run(
        request,
        db,
        principal,
        response,
        lambda: actions_service.postpone(
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
    principal: Approver,
    event_id: UUID,
    body: ReinstateIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Take back a cancellation or postponement."""
    return await _run(
        request,
        db,
        principal,
        response,
        lambda: actions_service.reinstate(
            db, principal, event_id, reason=body.reason, expected_rev=require_if_match(if_match)
        ),
    )


@alias_router.post(
    "/{event_id}/image-exception", response_model=EventOut, responses=_ERRORS, deprecated=True
)
@router.post("/image-exception", response_model=EventOut, responses=_ERRORS)
async def image_exception(
    request: Request,
    db: DbSession,
    principal: Granter,
    event_id: UUID,
    body: ImageExceptionIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Let this one event go public without a poster (editors only, audited)."""

    return await _run(
        request,
        db,
        principal,
        response,
        lambda: grant_image_exception(
            db, principal, event_id, body.reason, expected_rev=parse_if_match(if_match)
        ),
    )


@router.post("/assign-organization", response_model=EventOut, responses=_ERRORS)
async def assign_organization(
    request: Request,
    db: DbSession,
    principal: Assigner,
    event_id: UUID,
    body: AssignOrganizationIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Give a proposal its organization (editors only)."""
    return await _run(
        request,
        db,
        principal,
        response,
        lambda: assign.assign_organization(
            db, principal, event_id, body.organization_id, expected_rev=parse_if_match(if_match)
        ),
    )


@router.post("/revert-revision", response_model=EventOut, responses=_ERRORS)
async def revert_revision(
    request: Request,
    db: DbSession,
    principal: CriticalEditor,
    event_id: UUID,
    body: RevertIn,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Write a new revision with the content of an earlier one."""
    return await _run(
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


@router.post("/acknowledge-changes", response_model=EventOut, responses=_ERRORS)
async def acknowledge_changes(
    request: Request,
    db: DbSession,
    principal: CriticalEditor,
    event_id: UUID,
    response: Response,
    body: EmptyIn | None = None,
    if_match: IfMatch = None,
) -> EventOut:
    """Mark the text changes since the publication as seen."""
    return await _run(
        request,
        db,
        principal,
        response,
        lambda: marks.acknowledge_changes(
            db, principal, event_id, expected_rev=parse_if_match(if_match)
        ),
    )


@router.post("/confirm-flyer", response_model=EventOut, responses=_ERRORS)
async def confirm_flyer(
    request: Request,
    db: DbSession,
    principal: Editor,
    event_id: UUID,
    response: Response,
    body: EmptyIn | None = None,
    if_match: IfMatch = None,
) -> EventOut:
    """Record that the date on the flyer was checked."""
    return await _run(
        request,
        db,
        principal,
        response,
        lambda: marks.confirm_flyer(db, principal, event_id, expected_rev=parse_if_match(if_match)),
    )
