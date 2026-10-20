"""Inbox API: `/notifications` (own entries only; every signed-in person may call it)."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status

from app.deps import DbSession, Principal, require_principal
from app.modules.notifications import inbox
from app.modules.notifications.schemas import NotificationPage, UnreadCount
from app.shared.errors import NotFoundError, ProblemDetail

router = APIRouter(prefix="/notifications", tags=["notifications"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetail},
    404: {"model": ProblemDetail},
}
Member = Annotated[Principal, Depends(require_principal("library.read"))]


@router.get("", response_model=NotificationPage, responses=_ERRORS)
async def list_inbox(
    db: DbSession,
    principal: Member,
    unread: bool = False,
    limit: Annotated[int, Query(ge=1, le=inbox.MAX_LIMIT)] = inbox.DEFAULT_LIMIT,
    cursor: str | None = None,
) -> NotificationPage:
    """List the own notifications, newest first."""
    return await inbox.list_notifications(
        db, principal.sub, unread=unread, limit=limit, cursor=cursor
    )


@router.get("/unread-count", response_model=UnreadCount, responses=_ERRORS)
async def read_unread_count(db: DbSession, principal: Member) -> UnreadCount:
    """Count the unread notifications (cheap query for the bell)."""
    return UnreadCount(count=await inbox.unread_count(db, principal.sub))


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def read_all(db: DbSession, principal: Member) -> Response:
    """Mark every own notification read."""
    await inbox.mark_all_read(db, principal.sub)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT, responses=_ERRORS)
async def read_one(notification_id: UUID, db: DbSession, principal: Member) -> Response:
    """Mark one own notification read; a foreign or unknown id is a 404."""
    if not await inbox.mark_read(db, principal.sub, notification_id):
        raise NotFoundError("Notification not found.")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
