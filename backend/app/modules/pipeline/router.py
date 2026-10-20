"""Pipeline endpoints: fire a transition and list its guards."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response

from app.deps import DbSession, Principal, SettingsDep, require_principal
from app.modules.events.conflict import parse_if_match, require_if_match, set_etag, with_current
from app.modules.events.presenter import present
from app.modules.events.schemas import EventOut, TransitionIn, TransitionName
from app.modules.notifications.service import dispatch_mails
from app.modules.pipeline.actions import run_actions
from app.modules.pipeline.schemas import GuardsOut, reason_out
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
    428: _PROBLEM,
}

MANDATORY_IF_MATCH = frozenset({"T04", "T05"})
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


@router.post("/{event_id}/transitions/{transition}", response_model=EventOut, responses=_ERRORS)
async def fire_transition(
    request: Request,
    db: DbSession,
    settings: SettingsDep,
    principal: Reader,
    event_id: UUID,
    transition: TransitionName,
    response: Response,
    body: TransitionIn | None = None,
    if_match: IfMatch = None,
) -> EventOut:
    """Fire a transition; the service decides on the right in the organization of the dossier."""
    body = body or TransitionIn()
    service = PipelineService(db, editor_four_eyes=settings.editor_four_eyes)
    async with with_current(db, principal):
        fired = await service.stage_fire(
            principal,
            event_id,
            transition,
            note=body.note,
            publish_at=body.publish_at,
            expected_rev=(
                require_if_match(if_match)
                if transition in MANDATORY_IF_MATCH
                else parse_if_match(if_match)
            ),
        )
    out = (await present(db, principal, [fired.event]))[0]
    await db.commit()
    set_etag(response, out.rev)
    pool = getattr(request.app.state, "arq_pool", None)
    await run_actions(pool, fired.actions, fired.committed)
    await dispatch_mails(pool, fired.mails)
    return out


@router.get("/{event_id}/guards/{transition}", response_model=GuardsOut, responses=_ERRORS)
async def read_guards(
    db: DbSession,
    settings: SettingsDep,
    principal: Reader,
    event_id: UUID,
    transition: TransitionName,
) -> GuardsOut:
    """Show what is still missing before the click."""
    report = await PipelineService(db, editor_four_eyes=settings.editor_four_eyes).guards(
        principal, event_id, transition
    )
    return GuardsOut(
        transition=report.transition,
        allowed=report.allowed,
        reasons=[reason_out(r) for r in report.reasons],
    )
