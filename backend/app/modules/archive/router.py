"""Archive routes: read an archived dossier, clone a template, "last time", the template list."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.archive import clone, read
from app.modules.archive.last_time import last_time, panel
from app.modules.archive.schemas import (
    ArchiveEventOut,
    CloneIn,
    CloneOut,
    ClonePreviewOut,
    LastTimeOut,
    TemplateCard,
)
from app.modules.archive.templates import list_templates
from app.modules.events.access import load_visible
from app.modules.events.presenter import present
from app.modules.search.filters import Filters
from app.shared.errors import ProblemDetail
from app.shared.paging import DEFAULT_LIMIT, MAX_LIMIT, Page

router = APIRouter(tags=["archive"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Creator = Annotated[Principal, Depends(require_any_scope("event.create"))]


@router.get("/archive/{event_id}", response_model=ArchiveEventOut, responses=_ERRORS)
async def get_archive_event(db: DbSession, principal: Reader, event_id: UUID) -> ArchiveEventOut:
    """Read the core data, the shared documents and the clean shared files of a dossier."""
    return await read.archive_event(db, principal, event_id)


@router.post(
    "/events/{event_id}/clone",
    response_model=CloneOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def clone_event(
    db: DbSession, principal: Creator, event_id: UUID, body: CloneIn, response: Response
) -> CloneOut:
    """Create a dossier in `idea` from a template; the report lists what was taken over."""
    result = await clone.clone_event(db, principal, event_id, body)
    out = (await present(db, principal, [result.event]))[0]
    out.checklist_recomputed = result.recomputed
    await db.commit()
    response.headers["Location"] = f"/api/events/{out.id}"
    return CloneOut(event=out, report=result.report)


@router.get("/events/{event_id}/clone-preview", response_model=ClonePreviewOut, responses=_ERRORS)
async def clone_preview(
    db: DbSession,
    principal: Creator,
    event_id: UUID,
    organization_id: Annotated[UUID | None, Query(alias="organizationId")] = None,
) -> ClonePreviewOut:
    """Show what a clone would take over and what happened last time; nothing is written."""
    report = await clone.preview_clone(db, principal, event_id, organization_id)
    template = await clone.load_template(db, principal, event_id)
    return ClonePreviewOut(report=report, last_time=await panel(db, principal, template))


@router.get("/events/{event_id}/last-time", response_model=LastTimeOut | None, responses=_ERRORS)
async def get_last_time(db: DbSession, principal: Reader, event_id: UUID) -> LastTimeOut | None:
    """Show the previous edition's attendance and, for the own organization, costs and notes."""
    event = await load_visible(db, principal, event_id)
    return await last_time(db, principal, event)


@router.get("/templates", response_model=Page[TemplateCard], responses=_ERRORS)
async def get_templates(
    db: DbSession,
    principal: Reader,
    q: Annotated[str, Query(max_length=1000)] = "",
    category: Annotated[str | None, Query(max_length=100)] = None,
    organization: Annotated[str | None, Query(max_length=100)] = None,
    format: Annotated[str | None, Query(max_length=100)] = None,  # noqa: A002
    year: Annotated[int | None, Query(ge=1970, le=2200)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[TemplateCard]:
    """List the dossiers that may serve as templates, found with the shared search query."""
    filters = Filters(org=organization, year=year, category=category, format=format, clonable=True)
    cards, total = await list_templates(db, principal, q, filters, limit=limit, offset=offset)
    return Page(items=cards, total=total, limit=limit, offset=offset)
