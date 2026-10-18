"""Schemas of the taxonomy read API (camelCase on the wire)."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.modules.auth.schemas import CamelModel

CategoryKind = Literal["format", "fachschaft", "partner"]
ColorToken = Literal["orange", "blue", "petrol", "navy", "yellow", "red"]


class CategoryRef(CamelModel):
    """A short reference to a category."""

    id: UUID
    slug: str
    name: str
    kind: CategoryKind


class CategoryOut(CategoryRef):
    """An active category with its place in the tree and its presentation hints."""

    parent_id: UUID | None
    short: str | None
    color_token: ColorToken | None
    required_profile: Literal["generic", "party", "meeting", "trip"]
    sort: int


class CategoryNode(CategoryOut):
    """A category with its children (`?tree=true`)."""

    children: list[CategoryNode]


class VenueRef(CamelModel):
    """An active venue; the address of a private venue is left out."""

    id: UUID
    slug: str
    name: str
    address: str | None
    postcode: str | None
    city: str | None
    building_no: str | None
    room_key: str | None
