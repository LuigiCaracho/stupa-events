"""Revision history endpoints: the page of revisions and one revision with its snapshot."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.deps import DbSession, Principal, require_principal
from app.modules.events import revision_views
from app.modules.events.revision_views import RevisionDetail, RevisionOut
from app.shared.errors import ProblemDetail
from app.shared.paging import DEFAULT_LIMIT, MAX_LIMIT, Page

router = APIRouter(prefix="/events", tags=["revisions"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {401: _PROBLEM, 403: _PROBLEM, 404: _PROBLEM}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]


@router.get("/{event_id}/revisions", response_model=Page[RevisionOut], responses=_ERRORS)
async def list_revisions(
    db: DbSession,
    principal: Reader,
    event_id: UUID,
    field_class: Annotated[
        Literal["critical", "text", "dossier", "state"] | None, Query(alias="fieldClass")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
    min_rev: Annotated[int, Query(alias="minRev", ge=0)] = 0,
) -> Page[RevisionOut]:
    """List the revisions of a dossier, newest first."""
    items, total = await revision_views.list_revisions(
        db,
        principal,
        event_id,
        field_class=field_class,
        limit=limit,
        offset=offset,
        min_rev=min_rev,
    )
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/{event_id}/revisions/{rev}", response_model=RevisionDetail, responses=_ERRORS)
async def read_revision(
    db: DbSession, principal: Reader, event_id: UUID, rev: int
) -> RevisionDetail:
    """Read one revision with its snapshot."""
    return await revision_views.revision_detail(db, principal, event_id, rev)
