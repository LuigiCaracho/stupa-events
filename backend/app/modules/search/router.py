"""`GET /api/search`: the internal search over dossiers, documents and formats (I20)."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from app.deps import DbSession, Principal, require_principal
from app.modules.search import service
from app.modules.search.filters import Filters
from app.modules.search.schemas import SearchOut
from app.shared.antiabuse import rate_limit_search
from app.shared.errors import ProblemDetail

router = APIRouter(tags=["search"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 422, 429, 503)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]


@router.get(
    "/search",
    response_model=SearchOut,
    dependencies=[Depends(rate_limit_search)],
    responses=_ERRORS,
)
async def search(
    db: DbSession,
    principal: Reader,
    q: Annotated[str, Query(max_length=1000)] = "",
    scope: Annotated[Literal["events", "documents", "formats"], Query()] = "events",
    state: Annotated[list[str] | None, Query()] = None,
    org: Annotated[str | None, Query(max_length=100)] = None,
    year: Annotated[int | None, Query(ge=1970, le=2200)] = None,
    category: Annotated[str | None, Query(max_length=100)] = None,
    format: Annotated[str | None, Query(max_length=100)] = None,  # noqa: A002
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchOut:
    """Search by text and filters; the right filter runs in SQL before the text match."""
    filters = Filters(tuple(state or ()), org, year, category, format)
    return await service.search(db, principal, q, scope, filters, limit=limit, offset=offset)
