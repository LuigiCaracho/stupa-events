"""Category endpoints (`/admin/categories`, gate `taxonomy.manage`). The router commits.

A category is never deleted. The parent chain must stay a tree: a change that makes a
category its own ancestor is refused with `category_cycle`.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DbSession, Principal, require_principal
from app.modules.admin.patching import audit_config, changes, invalid, invalidate_feed, slug_taken
from app.modules.admin.schemas import AdminCategory, CategoryCreate, CategoryPatch
from app.modules.taxonomy.models import Category
from app.shared.errors import NotFoundError, ProblemDetail

router = APIRouter(prefix="/admin/categories", tags=["admin"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    422: _PROBLEM,
}
Manager = Annotated[Principal, Depends(require_principal("taxonomy.manage"))]
_NULLABLE = frozenset({"parent_id", "short", "color_token"})


async def _check_parent(db: AsyncSession, category_id: UUID | None, parent_id: UUID | None) -> None:
    """Refuse an unknown parent and any parent whose ancestor chain reaches the category."""
    seen: set[UUID] = set()
    cursor = parent_id
    while cursor is not None:
        if cursor == category_id or cursor in seen:
            raise invalid("parentId", "the parent chain would loop", "category_cycle")
        seen.add(cursor)
        parent = await db.get(Category, cursor)
        if parent is None:
            raise invalid("parentId", "unknown category")
        cursor = parent.parent_id


@router.get("", response_model=list[AdminCategory], responses=_ERRORS)
async def list_categories(db: DbSession, _: Manager):
    """List all categories, inactive ones included."""
    rows = await db.scalars(select(Category).order_by(Category.kind, Category.sort, Category.name))
    return list(rows)


@router.post(
    "", response_model=AdminCategory, status_code=status.HTTP_201_CREATED, responses=_ERRORS
)
async def create_category(db: DbSession, principal: Manager, body: CategoryCreate):
    """Create a category."""
    if await db.scalar(select(Category.id).where(Category.slug == body.slug)):
        raise slug_taken()
    await _check_parent(db, None, body.parent_id)
    category = Category(**body.model_dump())
    db.add(category)
    await db.flush()
    await db.refresh(category)
    await audit_config(db, principal.sub, "category", category.id, ["slug", *body.model_fields_set])
    await db.commit()
    return category


@router.patch("/{category_id}", response_model=AdminCategory, responses=_ERRORS)
async def patch_category(
    request: Request, db: DbSession, principal: Manager, category_id: UUID, body: CategoryPatch
):
    """Change a category (the slug never changes)."""
    category = await db.get(Category, category_id)
    if category is None:
        raise NotFoundError("category not found")
    values = changes(body, _NULLABLE)
    if "parent_id" in values:
        await _check_parent(db, category.id, values["parent_id"])
    for name, value in values.items():
        setattr(category, name, value)
    await db.flush()
    await db.refresh(category)
    await audit_config(db, principal.sub, "category", category.id, list(values))
    await db.commit()
    await invalidate_feed(request)
    return category
