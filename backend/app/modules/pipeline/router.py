"""Pipeline endpoints: fire a transition, list its guards, grant the image exception."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.auth.schemas import CamelModel
from app.modules.events.presenter import present
from app.modules.events.schemas import EventOut, ImageExceptionIn, TransitionIn, TransitionName
from app.modules.pipeline.actions import run_actions
from app.modules.pipeline.exception import grant_image_exception
from app.modules.pipeline.service import PipelineService
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/events", tags=["pipeline"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    422: _PROBLEM,
}

Actor = Annotated[
    Principal, Depends(require_any_scope("event.edit", "event.submit", "event.approve"))
]
Granter = Annotated[Principal, Depends(require_principal("event.image_exception"))]


class ReasonOut(CamelModel):
    """A blocker or warning of a guard."""

    code: str
    field: str | None
    severity: str
    message_key: str
    fix_action: str | None


class GuardsOut(CamelModel):
    """Guard list of a transition, computed on request and never stored."""

    transition: str
    allowed: bool
    reasons: list[ReasonOut]


@router.post("/{event_id}/transitions/{transition}", response_model=EventOut, responses=_ERRORS)
async def fire_transition(
    request: Request,
    db: DbSession,
    principal: Actor,
    event_id: UUID,
    transition: TransitionName,
    body: TransitionIn | None = None,
) -> EventOut:
    """Fire T01, T02, T04 or T05. A refusing guard answers 422 with `reasons[]`."""
    fired = await PipelineService(db).stage_fire(
        principal, event_id, transition, note=body.note if body else None
    )
    out = (await present(db, principal, [fired.event]))[0]
    await db.commit()
    await run_actions(getattr(request.app.state, "arq_pool", None), fired.actions, fired.committed)
    return out


@router.get("/{event_id}/guards/{transition}", response_model=GuardsOut, responses=_ERRORS)
async def read_guards(
    db: DbSession, principal: Actor, event_id: UUID, transition: TransitionName
) -> GuardsOut:
    """Show what is still missing before the click."""
    report = await PipelineService(db).guards(principal, event_id, transition)
    return GuardsOut(
        transition=report.transition,
        allowed=report.allowed,
        reasons=[
            ReasonOut(
                code=r.code,
                field=r.field,
                severity=r.severity.value,
                message_key=r.message_key,
                fix_action=r.fix_action.value if r.fix_action else None,
            )
            for r in report.reasons
        ],
    )


@router.post("/{event_id}/image-exception", response_model=EventOut, responses=_ERRORS)
async def image_exception(
    db: DbSession, principal: Granter, event_id: UUID, body: ImageExceptionIn
) -> EventOut:
    """Let this one event go public without a poster (editors only, audited)."""
    event = await grant_image_exception(db, principal, event_id, body.reason)
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    return out
