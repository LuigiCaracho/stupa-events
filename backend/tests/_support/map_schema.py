"""The JSON schemas of the map routes, generated from the wire models (contract file source)."""

from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from app.modules.publicapi.map_schemas import PublicCampusCollection, PublicMapCollection

ROOTS: dict[str, Any] = {"events": PublicMapCollection, "campus": PublicCampusCollection}


def generate() -> dict[str, Any]:
    """Return `{route: schema}` for the response bodies, in serialization (camelCase) mode."""
    return {
        name: TypeAdapter(model).json_schema(by_alias=True, mode="serialization")
        for name, model in ROOTS.items()
    }
