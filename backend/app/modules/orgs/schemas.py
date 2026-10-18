"""Schemas of the organization API (camelCase on the wire)."""

from __future__ import annotations

from uuid import UUID

from app.modules.auth.schemas import CamelModel


class OrgRef(CamelModel):
    """A short reference to an organization."""

    id: UUID
    slug: str
    name: str
    short: str
