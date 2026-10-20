"""Account API: `/account/notification-prefs` (own settings, every signed-in person)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.deps import DbSession, Principal, require_principal
from app.modules.account import service
from app.modules.account.schemas import PrefsIn, PrefsOut
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/account", tags=["account"])
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: {"model": ProblemDetail},
    422: {"model": ProblemDetail},
}
Member = Annotated[Principal, Depends(require_principal("library.read"))]


@router.get("/notification-prefs", response_model=PrefsOut, responses=_ERRORS)
async def get_notification_prefs(db: DbSession, principal: Member) -> PrefsOut:
    """Return the channel switches of all kinds."""
    return await service.read_prefs(db, principal.sub)


@router.put("/notification-prefs", response_model=PrefsOut, responses=_ERRORS)
async def put_notification_prefs(body: PrefsIn, db: DbSession, principal: Member) -> PrefsOut:
    """Save the switches of some kinds; an essential kind cannot go off."""
    service.validate_prefs(body.items)
    await service.write_prefs(db, principal.sub, body.items)
    await db.commit()
    return await service.read_prefs(db, principal.sub)
