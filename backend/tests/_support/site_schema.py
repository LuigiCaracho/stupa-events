"""The JSON schemas of the site routes, generated from the wire models (contract file source)."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from app.modules.publicapi.site_schemas import (
    PublicArchiveOut,
    PublicCalendarOut,
    PublicCategoryOut,
    PublicEventDetail,
    PublicSearchOut,
    PublicTodayOut,
)

ROOTS: dict[str, Any] = {
    "search": PublicSearchOut,
    "detail": PublicEventDetail,
    "today": PublicTodayOut,
    "categories": list[PublicCategoryOut],
    "calendar": PublicCalendarOut,
    "archive": PublicArchiveOut,
}


def generate() -> dict[str, Any]:
    """Return `{route: schema}` for the response bodies, in serialization (camelCase) mode."""
    return {
        name: TypeAdapter(model).json_schema(by_alias=True, mode="serialization")
        for name, model in ROOTS.items()
    }
