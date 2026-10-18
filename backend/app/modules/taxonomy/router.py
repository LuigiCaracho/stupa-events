"""Read-only lists of the categories and the venues, for the dialogs of the UI."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.deps import DbSession, require_principal
from app.modules.taxonomy.models import Category, Venue
from app.modules.taxonomy.schemas import CategoryNode, CategoryOut, VenueRef
from app.shared.errors import ProblemDetail

router = APIRouter(tags=["taxonomy"])
_READ = [Depends(require_principal("library.read"))]
_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {401: {"model": ProblemDetail}}


def build_tree(categories: list[CategoryOut]) -> list[CategoryNode]:
    """Nest the categories under their parents; a category without an active parent is a root."""
    nodes = {c.id: CategoryNode(**c.model_dump(), children=[]) for c in categories}
    roots: list[CategoryNode] = []
    for category in categories:
        node = nodes[category.id]
        parent = nodes.get(category.parent_id) if category.parent_id else None
        (parent.children if parent else roots).append(node)
    return roots


@router.get("/categories", dependencies=_READ, responses=_UNAUTHORIZED)
async def list_categories(
    db: DbSession, tree: Annotated[bool, Query()] = False
) -> list[CategoryNode] | list[CategoryOut]:
    """List the active categories by kind, sort and name; `tree=true` nests them."""
    rows = await db.scalars(
        select(Category)
        .where(Category.active.is_(True))
        .order_by(Category.kind, Category.sort, Category.name)
    )
    categories = [CategoryOut.model_validate(row) for row in rows]
    return build_tree(categories) if tree else categories


@router.get("/venues", response_model=list[VenueRef], dependencies=_READ, responses=_UNAUTHORIZED)
async def list_venues(db: DbSession) -> list[VenueRef]:
    """List the active venues by name; a private venue shows no address."""
    rows = await db.scalars(select(Venue).where(Venue.active.is_(True)).order_by(Venue.name))
    return [
        VenueRef.model_validate(row).model_copy(
            update={"address": None, "postcode": None, "city": None} if row.is_private else {}
        )
        for row in rows
    ]
