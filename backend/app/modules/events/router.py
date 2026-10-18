"""Event endpoints: list, create (T00), read and patch. The router commits."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.events.presenter import present
from app.modules.events.schemas import EventCreate, EventOut, EventPatch
from app.modules.events.service import EventService
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
}

Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Creator = Annotated[Principal, Depends(require_any_scope("event.create"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]


@router.get("", response_model=Page[EventOut], responses=_ERRORS)
async def list_events(
    db: DbSession,
    principal: Reader,
    state: Annotated[str | None, Query()] = None,
    organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[EventOut]:
    """List the dossiers the caller reads, ascending by start time."""
    rows, total = await EventService(db).list_events(
        principal, state=state, organization_id=organization_id, q=q, limit=limit, offset=offset
    )
    return Page(items=await present(db, principal, rows), total=total, limit=limit, offset=offset)


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS)
async def create_event(db: DbSession, principal: Creator, body: EventCreate) -> EventOut:
    """Create a dossier in `idea` (T00) in an organization of the caller."""
    event = await EventService(db).create(principal, body)
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    return out


@router.get("/{event_id}", response_model=EventOut, responses=_ERRORS)
async def get_event(db: DbSession, principal: Reader, event_id: UUID) -> EventOut:
    """Read one dossier; 404 without a read right."""
    event = await EventService(db).get(principal, event_id)
    return (await present(db, principal, [event]))[0]


@router.patch("/{event_id}", response_model=EventOut, responses=_ERRORS)
async def patch_event(
    db: DbSession, principal: Editor, event_id: UUID, body: EventPatch
) -> EventOut:
    """Change fields of a dossier in `idea` or `planning`; `rev` must be current."""
    event = await EventService(db).patch(principal, event_id, body)
    out = (await present(db, principal, [event]))[0]
    await db.commit()
    return out
