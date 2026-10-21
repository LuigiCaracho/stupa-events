"""Check the defaults of a format: the category and the venue must exist and be active."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.formats.schemas import FormatDefaults
from app.modules.taxonomy.models import Category, Venue
from app.shared.errors import FieldError, ValidationProblem


async def stored_defaults(session: AsyncSession, defaults: FormatDefaults) -> dict[str, Any]:
    """Return the JSON stored in `format.defaults` after checking the references.

    Raises:
        ValidationProblem: `unknown_category` or `unknown_venue` for a missing or inactive row.
    """
    for model, ident, field, code in (
        (Category, defaults.category_id, "defaults.categoryId", "unknown_category"),
        (Venue, defaults.venue_id, "defaults.venueId", "unknown_venue"),
    ):
        row = await session.get(model, ident) if ident else None
        if ident and (row is None or not row.active):
            raise ValidationProblem(
                "Invalid request.", code=code, errors=[FieldError(field=field, msg="unknown")]
            )
    return defaults.model_dump(by_alias=True, exclude_none=True, mode="json")
