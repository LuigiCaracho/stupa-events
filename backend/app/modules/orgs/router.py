"""Read-only list of the organizations, for the create dialog of the UI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, require_principal
from app.modules.auth.principal import Principal
from app.modules.orgs.models import Organization
from app.modules.orgs.schemas import OrgRef
from app.modules.orgs.scope import bind
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get(
    "",
    response_model=list[OrgRef],
    responses={401: {"model": ProblemDetail}},
)
async def list_organizations(
    db: DbSession,
    principal: Annotated[Principal, Depends(require_principal("library.read"))],
    creatable: bool = False,
) -> list[OrgRef]:
    """List the active organizations, sorted by name.

    With `creatable` the list holds only the organizations in which the caller holds
    `event.create`.
    """
    await bind(db, principal)
    rows = (
        (
            await db.execute(
                select(Organization)
                .where(Organization.active.is_(True))
                .order_by(Organization.name)
            )
        )
        .scalars()
        .all()
    )
    return [
        OrgRef.model_validate(row)
        for row in rows
        if not creatable or principal.has("event.create", row.id)
    ]
