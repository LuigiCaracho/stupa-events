"""Test factories: settings, principals and a tiny PNG."""

from __future__ import annotations

import io
from typing import Any

from app.modules.auth.principal import Principal
from app.settings import Settings, load_settings
from app.shared.permissions import grants_from_groups, permissions_of


def make_settings(**overrides: Any) -> Settings:
    """Build settings with test defaults; `overrides` win."""
    base: dict[str, Any] = {
        "database_url": "postgresql+asyncpg://app:pw@localhost/events_test",
        "session_secret": "test-session-secret",
        "rate_limit_enabled": False,
    }
    return load_settings(**{**base, **overrides})


def make_principal(*groups: str, sub: str = "sub-1", admin: bool = False) -> Principal:
    """Build a principal from IdP group names, the way the resolver does."""
    grants = grants_from_groups(groups)
    global_roles = {"member", *(g.role for g in grants if g.org is None)}
    if admin:
        global_roles.add("admin")
    org_roles: dict[str, set[str]] = {}
    for grant in grants:
        if grant.org is not None:
            org_roles.setdefault(grant.org, set()).add(grant.role)
    return Principal(
        sub=sub,
        roles=sorted(global_roles),
        permissions=set(permissions_of(global_roles)),
        groups=set(groups),
        org_roles={slug: frozenset(roles) for slug, roles in org_roles.items()},
    )


def png_bytes(width: int = 1280, height: int = 720, color: str = "#3366cc") -> bytes:
    """Return a valid PNG, poster-sized by default (long edge 1280 px)."""
    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, "PNG")
    return buffer.getvalue()
