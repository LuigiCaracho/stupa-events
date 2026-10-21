"""Checklist routes: read, apply a template, add, change, finish and delete items."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.dossier import checklist
from app.modules.dossier.schemas_checklist import (
    ApplyTemplateIn,
    ChecklistItemCreate,
    ChecklistItemOut,
    ChecklistItemPatch,
    ChecklistOut,
    DoneIn,
)
from app.shared.errors import ProblemDetail

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Editor = Annotated[Principal, Depends(require_any_scope("event.edit"))]

router = APIRouter(tags=["checklist"])


@router.get("/events/{event_id}/checklist", response_model=ChecklistOut, responses=_ERRORS)
async def get_checklist(db: DbSession, principal: Reader, event_id: UUID) -> ChecklistOut:
    """Return the checklist with the open required counts per phase."""
    return await checklist.checklist(db, principal, event_id)


@router.post(
    "/events/{event_id}/checklist/apply-template", response_model=ChecklistOut, responses=_ERRORS
)
async def apply_template(
    db: DbSession, principal: Editor, event_id: UUID, body: ApplyTemplateIn
) -> ChecklistOut:
    """Copy the template items that are still missing (idempotent)."""
    out = await checklist.apply_template(db, principal, event_id, body.template_slug)
    await db.commit()
    return out


@router.post(
    "/events/{event_id}/checklist/items",
    response_model=ChecklistItemOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def add_item(
    db: DbSession, principal: Editor, event_id: UUID, body: ChecklistItemCreate
) -> ChecklistItemOut:
    """Add a free item to the checklist."""
    out = await checklist.add_item(db, principal, event_id, body)
    await db.commit()
    return out


@router.patch("/checklist-items/{item_id}", response_model=ChecklistItemOut, responses=_ERRORS)
async def patch_item(
    db: DbSession, principal: Editor, item_id: UUID, body: ChecklistItemPatch
) -> ChecklistItemOut:
    """Change an item; `dueAt: null` hands the date back to the start rule."""
    out = await checklist.patch_item(db, principal, item_id, body)
    await db.commit()
    return out


@router.post("/checklist-items/{item_id}/done", response_model=ChecklistItemOut, responses=_ERRORS)
async def done_item(
    db: DbSession, principal: Reader, item_id: UUID, body: DoneIn
) -> ChecklistItemOut:
    """Finish an item or open it again (editors and the assigned person)."""
    out = await checklist.set_done(db, principal, item_id, body.done)
    await db.commit()
    return out


@router.delete(
    "/checklist-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS
)
async def delete_item(db: DbSession, principal: Editor, item_id: UUID) -> Response:
    """Delete a free item."""
    await checklist.delete_item(db, principal, item_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
