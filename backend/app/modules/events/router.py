"""Event endpoints: list and board, create (T00), read and patch. The router commits."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.deps import DbSession, Principal, SettingsDep, require_any_scope, require_principal
from app.modules.events.calendar import CalendarOut, calendar, check_range
from app.modules.events.card_schemas import BoardOut, EventCard
from app.modules.events.conflict import revision_of, set_etag, with_current
from app.modules.events.listing import Filters, board, list_cards
from app.modules.events.presenter import present
from app.modules.events.schemas import EventCreate, EventOut, EventPatch
from app.modules.events.service import EventService
from app.modules.pipeline.actions import run_actions
from app.shared.errors import ProblemDetail
from app.shared.paging import DEFAULT_LIMIT, MAX_LIMIT, Page

router = APIRouter(prefix="/events", tags=["events"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    422: _PROBLEM,
    428: _PROBLEM,
}

Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]
IfMatch = Annotated[str | None, Header(alias="If-Match")]


@router.get("", response_model=Page[EventCard] | BoardOut | CalendarOut, responses=_ERRORS)
async def list_events(
    db: DbSession,
    principal: Reader,
    view: Annotated[Literal["list", "board", "calendar"], Query()] = "list",
    state: Annotated[list[str] | None, Query()] = None,
    organization: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    mine: Annotated[bool, Query()] = False,
    q: Annotated[str | None, Query(max_length=200)] = None,
    from_: Annotated[date | None, Query(alias="from")] = None,
    to: Annotated[date | None, Query()] = None,
    sort: Annotated[Literal["startsAt", "-startsAt"], Query()] = "startsAt",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
    column_limit: Annotated[int, Query(alias="columnLimit", ge=1, le=100)] = 50,
) -> Page[EventCard] | BoardOut | CalendarOut:
    """List the dossiers the caller reads as cards, build the board or fill the calendar."""
    if view == "calendar":
        first, last = check_range(from_, to)
        return await calendar(
            db, principal, Filters(tuple(state or ()), organization, category, mine, q), first, last
        )
    filters = Filters(tuple(state or ()), organization, category, mine, q, from_, to)
    if view == "board":
        return await board(db, principal, filters, column_limit=column_limit)
    cards, total = await list_cards(
        db, principal, filters, descending=sort == "-startsAt", limit=limit, offset=offset
    )
    return Page(items=cards, total=total, limit=limit, offset=offset)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def create_event(
    db: DbSession, settings: SettingsDep, principal: Reader, body: EventCreate, response: Response
) -> EventOut:
    """Create a dossier in `idea` (T00): in an organization of the caller, or as a proposal."""
    event = await EventService(db, editor_four_eyes=settings.editor_four_eyes).create(
        principal, body
    )
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    set_etag(response, out.rev)
    return out


@router.get("/{event_id}", response_model=EventOut, responses=_ERRORS)
async def get_event(
    db: DbSession, principal: Reader, event_id: UUID, response: Response
) -> EventOut:
    """Read one dossier; 404 without a read right."""
    event = await EventService(db).get(principal, event_id)
    out = (await present(db, principal, [event]))[0]
    set_etag(response, out.rev)
    return out


@router.patch("/{event_id}", response_model=EventOut, responses=_ERRORS)
async def patch_event(
    request: Request,
    db: DbSession,
    settings: SettingsDep,
    principal: Editor,
    event_id: UUID,
    body: EventPatch,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Change fields by their class and the state; `If-Match` (or `rev`) must be current."""
    expected = revision_of(if_match, body.rev)
    service = EventService(db, editor_four_eyes=settings.editor_four_eyes)
    async with with_current(db, principal):
        event, actions, committed = await service.patch(principal, event_id, body, expected)
    out = (await present(db, principal, [event]))[0]
    out.checklist_recomputed = db.info.pop("checklist_recomputed", None)
    out.facts_dropped = db.info.pop("facts_dropped", None)
    await db.commit()
    set_etag(response, out.rev)
    await run_actions(getattr(request.app.state, "arq_pool", None), actions, committed)
    return out
