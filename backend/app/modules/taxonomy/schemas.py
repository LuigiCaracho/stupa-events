"""Schemas of the taxonomy API (camelCase on the wire)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.modules.auth.schemas import CamelModel


class CategoryRef(CamelModel):
    """A short reference to a category."""

    id: UUID
    slug: str
    name: str
    kind: Literal["format", "fachschaft", "partner"]
