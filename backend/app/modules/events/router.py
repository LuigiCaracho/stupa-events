"""Event endpoints: list and calendar, create, read, hints and patch. The router commits."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.events.access import load_visible, poster_of
from app.modules.events.calendar import CalendarOut, calendar, check_range
from app.modules.events.card_schemas import EventCard
from app.modules.events.conflict import revision_of, set_etag, with_current
from app.modules.events.hints import missing_info
from app.modules.events.hints_data import hint_inputs
from app.modules.events.listing import Filters, list_cards
from app.modules.events.postcommit import run_actions
from app.modules.events.presenter import present
from app.modules.events.schemas import EventCreate, EventOut, EventPatch, HintOut, HintsOut
from app.modules.events.service import EventService
from app.modules.taxonomy.models import Category
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


@router.get("", response_model=Page[EventCard] | CalendarOut, responses=_ERRORS)
async def list_events(
    db: DbSession,
    principal: Reader,
    view: Annotated[Literal["list", "calendar"], Query()] = "list",
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
) -> Page[EventCard] | CalendarOut:
    """List the dossiers the caller reads as cards or fill the calendar."""
    if view == "calendar":
        first, last = check_range(from_, to)
        return await calendar(
            db, principal, Filters(tuple(state or ()), organization, category, mine, q), first, last
        )
    filters = Filters(tuple(state or ()), organization, category, mine, q, from_, to)
    cards, total = await list_cards(
        db, principal, filters, descending=sort == "-startsAt", limit=limit, offset=offset
    )
    return Page(items=cards, total=total, limit=limit, offset=offset)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def create_event(
    db: DbSession, principal: Reader, body: EventCreate, response: Response
) -> EventOut:
    """Create a draft in an organization where the caller holds `event.create`."""
    event = await EventService(db).create(principal, body)
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


@router.get("/{event_id}/hints", response_model=HintsOut, responses=_ERRORS)
async def get_hints(db: DbSession, principal: Reader, event_id: UUID) -> HintsOut:
    """List what the dossier still lacks: hints, never locks."""
    event = await load_visible(db, principal, event_id)
    poster = await poster_of(db, event)
    category = (
        await db.get(Category, event.primary_category_id) if event.primary_category_id else None
    )
    inputs = await hint_inputs(
        db,
        [event],
        {poster.id: poster} if poster else {},
        {category.id: category} if category else {},
    )
    hints = missing_info(inputs[event.id])
    return HintsOut(items=[HintOut(code=h.code, severity=h.severity, field=h.field) for h in hints])


@router.patch("/{event_id}", response_model=EventOut, responses=_ERRORS)
async def patch_event(
    request: Request,
    db: DbSession,
    principal: Editor,
    event_id: UUID,
    body: EventPatch,
    response: Response,
    if_match: IfMatch = None,
) -> EventOut:
    """Change fields by their class and the state; `If-Match` (or `rev`) must be current."""
    expected = revision_of(if_match, body.rev)
    service = EventService(db)
    async with with_current(db, principal):
        event, actions, committed = await service.patch(principal, event_id, body, expected)
    out = (await present(db, principal, [event]))[0]
    out.checklist_recomputed = db.info.pop("checklist_recomputed", None)
    out.facts_dropped = db.info.pop("facts_dropped", None)
    await db.commit()
    set_etag(response, out.rev)
    await run_actions(getattr(request.app.state, "arq_pool", None), actions, committed)
    return out
