"""Quote routes: groups, add, change, select and hide."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.dossier import quotes
from app.modules.dossier.schemas_quotes import QuoteCreate, QuoteOut, QuotePatch, QuotesOut
from app.shared.errors import ProblemDetail

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Attacher = Annotated[Principal, Depends(require_any_scope("dossier.attach"))]

router = APIRouter(tags=["quotes"])


@router.get("/events/{event_id}/quotes", response_model=QuotesOut, responses=_ERRORS)
async def list_quotes(
    db: DbSession,
    principal: Reader,
    event_id: UUID,
    include_retired: Annotated[bool, Query(alias="includeRetired")] = False,
) -> QuotesOut:
    """Return the comparison quotes by group with the selected totals."""
    return await quotes.list_quotes(db, principal, event_id, include_retired=include_retired)


@router.post(
    "/events/{event_id}/quotes",
    response_model=QuoteOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def create_quote(
    db: DbSession, principal: Attacher, event_id: UUID, body: QuoteCreate
) -> QuoteOut:
    """Add a quote to a comparison group."""
    out = await quotes.create(db, principal, event_id, body)
    await db.commit()
    return out


@router.patch("/quotes/{quote_id}", response_model=QuoteOut, responses=_ERRORS)
async def patch_quote(
    db: DbSession, principal: Attacher, quote_id: UUID, body: QuotePatch
) -> QuoteOut:
    """Change a quote."""
    out = await quotes.patch(db, principal, quote_id, body)
    await db.commit()
    return out


@router.post("/quotes/{quote_id}/select", response_model=QuoteOut, responses=_ERRORS)
async def select_quote(db: DbSession, principal: Attacher, quote_id: UUID) -> QuoteOut:
    """Select a quote; the others of its group are deselected."""
    out = await quotes.select_quote(db, principal, quote_id)
    await db.commit()
    return out


@router.delete("/quotes/{quote_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def retire_quote(db: DbSession, principal: Attacher, quote_id: UUID) -> Response:
    """Hide a quote."""
    await quotes.retire(db, principal, quote_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
