"""Organization endpoints (`/admin/organizations`, gate `taxonomy.manage`). The router commits.

`trusted` changes who may approve, so it needs `admin.mappings` on top and runs the
membership sync in the same transaction. Deactivating an organization (or reviving it)
runs the sync too, because roles of an inactive organization are ignored.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DbSession, Principal, require_principal
from app.modules.admin.membership_sync import sync_all_memberships
from app.modules.admin.patching import audit_config, changes, invalid, invalidate_feed, slug_taken
from app.modules.admin.schemas import AdminOrganization, OrganizationCreate, OrganizationPatch
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.orgs.models import Organization
from app.modules.taxonomy.models import Category
from app.shared.errors import ForbiddenError, NotFoundError, ProblemDetail

router = APIRouter(prefix="/admin/organizations", tags=["admin"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    422: _PROBLEM,
}
Manager = Annotated[Principal, Depends(require_principal("taxonomy.manage"))]
_NULLABLE = frozenset({"parent_id", "color_token", "category_id"})


async def _check_parent(db: AsyncSession, org_id: UUID | None, parent_id: UUID | None) -> None:
    """Refuse an unknown parent and any parent whose ancestor chain reaches the organization."""
    seen: set[UUID] = set()
    cursor = parent_id
    while cursor is not None:
        if cursor == org_id or cursor in seen:
            raise invalid("parentId", "the parent chain would loop", "organization_cycle")
        seen.add(cursor)
        parent = await db.get(Organization, cursor)
        if parent is None:
            raise invalid("parentId", "unknown organization")
        cursor = parent.parent_id


async def _check_references(
    db: AsyncSession, org_id: UUID | None, parent_id: UUID | None, category_id: UUID | None
) -> None:
    await _check_parent(db, org_id, parent_id)
    if category_id is not None and await db.get(Category, category_id) is None:
        raise invalid("categoryId", "unknown category")


async def _audit_trust(db: AsyncSession, actor: str, org: Organization) -> None:
    await audit_record(
        db,
        actor=actor,
        action=AuditAction.ROLE_MAPPING_CHANGE,
        target_type="organization",
        target_id=str(org.id),
        data={"trusted": org.trusted},
    )
    await sync_all_memberships(db)


@router.get("", response_model=list[AdminOrganization], responses=_ERRORS)
async def list_organizations(db: DbSession, _: Manager):
    """List all organizations, inactive ones included."""
    rows = await db.scalars(select(Organization).order_by(Organization.name))
    return list(rows)


@router.post(
    "", response_model=AdminOrganization, status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def create_organization(db: DbSession, principal: Manager, body: OrganizationCreate):
    """Create an organization; `trusted=true` needs `admin.mappings`."""
    if body.trusted and not principal.has("admin.mappings"):
        raise ForbiddenError("Missing permission: admin.mappings")
    if await db.scalar(select(Organization.id).where(Organization.slug == body.slug)):
        raise slug_taken()
    await _check_references(db, None, body.parent_id, body.category_id)
    org = Organization(**body.model_dump())
    db.add(org)
    await db.flush()
    await db.refresh(org)
    await audit_config(db, principal.sub, "organization", org.id, ["slug", *body.model_fields_set])
    if org.trusted:
        await _audit_trust(db, principal.sub, org)
    await db.commit()
    return org


@router.patch("/{organization_id}", response_model=AdminOrganization, responses=_ERRORS)
async def patch_organization(
    request: Request,
    db: DbSession,
    principal: Manager,
    organization_id: UUID,
    body: OrganizationPatch,
):
    """Change an organization; `trusted` needs `admin.mappings` when its value changes."""
    org = await db.get(Organization, organization_id)
    if org is None:
        raise NotFoundError("organization not found")
    values = changes(body, _NULLABLE)
    trust_changes = "trusted" in values and values["trusted"] != org.trusted
    active_changes = "active" in values and values["active"] != org.active
    if trust_changes and not principal.has("admin.mappings"):
        raise ForbiddenError("Missing permission: admin.mappings")
    await _check_references(db, org.id, values.get("parent_id"), values.get("category_id"))
    for name, value in values.items():
        setattr(org, name, value)
    await db.flush()
    await db.refresh(org)
    await audit_config(db, principal.sub, "organization", org.id, list(values))
    if trust_changes:
        await _audit_trust(db, principal.sub, org)
    elif active_changes:
        await sync_all_memberships(db)
    await db.commit()
    await invalidate_feed(request)
    return org
