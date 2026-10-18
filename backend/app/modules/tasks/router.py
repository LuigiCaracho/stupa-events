"""`GET /api/tasks`: what the signed-in person can act on now."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.deps import DbSession, Principal, require_principal
from app.modules.tasks.schemas import TasksOut
from app.modules.tasks.service import build_tasks
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/tasks", tags=["tasks"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetail},
    403: {"model": ProblemDetail},
}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]


@router.get("", response_model=TasksOut, responses=_ERRORS)
async def read_tasks(db: DbSession, principal: Reader) -> TasksOut:
    """List the dossiers that wait for the caller, grouped by reason."""
    return await build_tasks(db, principal)
