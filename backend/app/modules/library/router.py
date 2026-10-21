"""Library routes (I19): the list with facets and "adopt into dossier"."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.auth.schemas import CamelModel
from app.modules.dossier.schemas_documents import DocumentOut
from app.modules.library import service
from app.modules.library.schemas import LibraryPage
from app.modules.search.filters import Filters
from app.shared.errors import ProblemDetail
from app.shared.paging import DEFAULT_LIMIT, MAX_LIMIT

router = APIRouter(prefix="/library", tags=["library"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]


class AdoptIn(CamelModel):
    """Body of `adopt`: the dossier that receives the copy."""

    event_id: UUID


@router.get("", response_model=LibraryPage, responses=_ERRORS)
async def get_library(
    db: DbSession,
    principal: Reader,
    q: Annotated[str, Query(max_length=1000)] = "",
    kind: Annotated[Literal["document", "attachment"] | None, Query()] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    organization: Annotated[str | None, Query(max_length=100)] = None,
    year: Annotated[int | None, Query(ge=1970, le=2200)] = None,
    format: Annotated[str | None, Query(max_length=100)] = None,  # noqa: A002
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> LibraryPage:
    """List what was shared on purpose: documents, files and master howtos."""
    filters = Filters(org=organization, year=year, category=category, format=format, kind=kind)
    return await service.list_library(db, principal, q, filters, limit=limit, offset=offset)


@router.post(
    "/documents/{document_id}/adopt",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def adopt_document(
    db: DbSession, principal: Editor, document_id: UUID, body: AdoptIn
) -> DocumentOut:
    """Copy a library document into a dossier; files are not copied."""
    out = await service.adopt(db, principal, document_id, body.event_id)
    await db.commit()
    return out
