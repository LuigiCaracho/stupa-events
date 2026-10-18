"""Pydantic schemas for the auth module (camelCase on the wire, `extra=forbid`).

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/schemas.py (events `Me`)
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Base model that emits camelCase JSON and refuses unknown fields."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", from_attributes=True
    )


class LogoutOut(CamelModel):
    """Result of an RP-initiated logout.

    With OIDC, `logout_url` ends the SSO session at the IdP. The frontend must redirect
    the browser there. A purely local logout gives `null`.
    """

    logout_url: str | None = None


class OrgRoleOut(CamelModel):
    """One organization membership of the principal."""

    slug: str
    role: str


class MeOut(CamelModel):
    """The principal with its resolved roles, permissions, groups and organizations."""

    sub: str
    email: str | None = None
    display_name: str | None = None
    roles: list[str]
    permissions: list[str]
    groups: list[str]
    organizations: list[OrgRoleOut]
