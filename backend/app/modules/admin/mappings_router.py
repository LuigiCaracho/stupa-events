"""Group mapping endpoints (`/admin/group-mappings`, gate `admin.mappings`). The router commits.

Pattern from STUPA-Workflow@93c33d6 backend/app/modules/admin/oidc_mappings.py
(rewritten for events roles, no code copied).
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status

from app.deps import DbSession, Principal, SettingsDep, require_principal
from app.modules.admin.mappings_service import MappingService
from app.modules.admin.schemas import GroupMappingCreate, GroupMappingOut, GroupMappingPatch
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/admin/group-mappings", tags=["admin"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    422: _PROBLEM,
}
Admin = Annotated[Principal, Depends(require_principal("admin.mappings"))]


@router.get("", response_model=list[GroupMappingOut], responses=_ERRORS)
async def list_mappings(db: DbSession, settings: SettingsDep, principal: Admin):
    """List the mappings with the number of people in each group."""
    return await MappingService(db, settings, principal.sub).list()


@router.post(
    "", response_model=GroupMappingOut, status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def create_mapping(
    db: DbSession, settings: SettingsDep, principal: Admin, body: GroupMappingCreate
):
    """Map an IdP group to a role, globally or in one organization."""
    out = await MappingService(db, settings, principal.sub).create(body)
    await db.commit()
    return out


@router.post("/defaults", response_model=list[GroupMappingOut], responses=_ERRORS)
async def create_default_mappings(db: DbSession, settings: SettingsDep, principal: Admin):
    """Create the proposed mappings that are missing; return the new rows."""
    out = await MappingService(db, settings, principal.sub).create_defaults()
    await db.commit()
    return out


@router.patch("/{mapping_id}", response_model=GroupMappingOut, responses=_ERRORS)
async def update_mapping(
    db: DbSession,
    settings: SettingsDep,
    principal: Admin,
    mapping_id: UUID,
    body: GroupMappingPatch,
):
    """Change the role or the organization of a mapping."""
    out = await MappingService(db, settings, principal.sub).update(mapping_id, body)
    await db.commit()
    return out


@router.delete(
    "/{mapping_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    responses=_ERRORS,
)
async def delete_mapping(
    db: DbSession, settings: SettingsDep, principal: Admin, mapping_id: UUID
) -> Response:
    """Delete a mapping."""
    await MappingService(db, settings, principal.sub).delete(mapping_id)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
