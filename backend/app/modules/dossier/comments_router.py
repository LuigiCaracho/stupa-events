"""Comment routes: threads, add, resolve, reopen."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.dossier import comments
from app.modules.dossier.deps import ArqPool
from app.modules.dossier.schemas_comments import CommentCreate, CommentOut, ThreadOut
from app.modules.notifications.service import dispatch_mails
from app.shared.errors import ProblemDetail

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {c: _PROBLEM for c in (401, 403, 404, 409, 422)}
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Writer = Annotated[Principal, Depends(require_any_scope("comment.write"))]

router = APIRouter(tags=["comments"])


@router.get("/events/{event_id}/comments", response_model=list[ThreadOut], responses=_ERRORS)
async def list_comments(
    db: DbSession,
    principal: Reader,
    event_id: UUID,
    only_open: Annotated[bool, Query(alias="open")] = False,
) -> list[ThreadOut]:
    """Return the comment threads of a dossier; `open=true` keeps the open roots."""
    return await comments.threads(db, principal, event_id, only_open=only_open)


@router.post(
    "/events/{event_id}/comments",
    response_model=CommentOut,
    status_code=status.HTTP_201_CREATED,
    responses=_ERRORS,
)
async def create_comment(
    db: DbSession, pool: ArqPool, principal: Writer, event_id: UUID, body: CommentCreate
) -> CommentOut:
    """Add a comment or a reply; the dossier's people are notified."""
    _, out, pending = await comments.create(db, principal, event_id, body)
    await db.commit()
    await dispatch_mails(pool, pending)
    return out


@router.post("/comments/{comment_id}/resolve", response_model=CommentOut, responses=_ERRORS)
async def resolve_comment(
    db: DbSession, pool: ArqPool, principal: Reader, comment_id: UUID
) -> CommentOut:
    """Resolve a root comment (idempotent)."""
    out, pending = await comments.resolve(db, principal, comment_id)
    await db.commit()
    await dispatch_mails(pool, pending)
    return out


@router.post("/comments/{comment_id}/reopen", response_model=CommentOut, responses=_ERRORS)
async def reopen_comment(db: DbSession, principal: Reader, comment_id: UUID) -> CommentOut:
    """Reopen a resolved root comment."""
    out = await comments.reopen(db, principal, comment_id)
    await db.commit()
    return out
