"""Read-only list of the categories, for the create dialog of the UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.deps import DbSession, require_principal
from app.modules.taxonomy.models import Category
from app.modules.taxonomy.schemas import CategoryRef
from app.shared.errors import ProblemDetail

router = APIRouter(prefix="/categories", tags=["taxonomy"])


@router.get(
    "",
    response_model=list[CategoryRef],
    dependencies=[Depends(require_principal("library.read"))],
    responses={401: {"model": ProblemDetail}},
)
async def list_categories(db: DbSession) -> list[CategoryRef]:
    """List the active categories, sorted by kind and name."""
    rows = (
        (
            await db.execute(
                select(Category)
                .where(Category.active.is_(True))
                .order_by(Category.kind, Category.sort, Category.name)
            )
        )
        .scalars()
        .all()
    )
    return [CategoryRef.model_validate(row) for row in rows]
