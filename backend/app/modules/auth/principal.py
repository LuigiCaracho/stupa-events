"""Core auth type: the resolved `Principal` and its single decision point `has`.

This is a leaf module. It imports nothing from `app.deps`, which breaks the import cycle
between `app.deps` and this package. `app.deps` re-exports `Principal`.

The principal carries the organizations as slugs only. The slug to id mapping lives in
`app.modules.orgs.scope`, which binds it once per request with `bind_org_ids`.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/principal.py (org-scoped has)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.shared.permissions import permissions_of


@dataclass(slots=True)
class Principal:
    """An OIDC member with resolved roles, permissions, groups and organization roles."""

    sub: str
    email: str | None = None
    display_name: str | None = None
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)
    groups: set[str] = field(default_factory=set)
    org_roles: dict[str, frozenset[str]] = field(default_factory=dict)
    org_ids: dict[str, str] = field(default_factory=dict)
    scope_permissions: frozenset[str] | None = None

    def has(self, perm: str, org_id: UUID | str | None = None) -> bool:
        """Decide whether the principal holds `perm`, globally or in one organization.

        The order is fixed: the scope cap of a token first, then the admin bypass, then
        the global permissions, then the permissions of the roles in the organization
        `org_id`. An organization that `bind_org_ids` did not bind never matches, so an
        unbound principal fails closed. Never decide a right from `roles`.
        """
        if self.scope_permissions is not None and perm not in self.scope_permissions:
            return False
        if "admin" in self.roles or perm in self.permissions:
            return True
        if org_id is None:
            return False
        return any(
            perm in permissions_of(roles)
            for slug, roles in self.org_roles.items()
            if self.org_ids.get(slug) == str(org_id)
        )

    def has_in_org(self, perm: str, slug: str) -> bool:
        """Decide whether the principal holds `perm` in the organization with this slug."""
        if self.scope_permissions is not None and perm not in self.scope_permissions:
            return False
        if "admin" in self.roles or perm in self.permissions:
            return True
        return perm in permissions_of(self.org_roles.get(slug, frozenset()))

    def org_slugs_with(self, perm: str) -> set[str]:
        """Return the slugs of the organizations in which only an org role grants `perm`."""
        return {slug for slug, roles in self.org_roles.items() if perm in permissions_of(roles)}

    def bind_org_ids(self, mapping: dict[str, UUID | str]) -> None:
        """Bind organization slugs to their ids so that `has(perm, org_id)` can match."""
        self.org_ids = {slug: str(org_id) for slug, org_id in mapping.items()}

    @property
    def is_admin(self) -> bool:
        """Tell if the principal holds the global `admin` role (no scope cap applied)."""
        return "admin" in self.roles

    def scope_allows(self, perm: str) -> bool:
        """Tell if the token scope cap lets `perm` through (a session lets all through)."""
        return self.scope_permissions is None or perm in self.scope_permissions

    def in_group(self, group: str) -> bool:
        """Tell if the IdP delivered the group."""
        return group in self.groups

    @property
    def organizations(self) -> list[tuple[str, str]]:
        """Return the `(slug, role)` pairs of the organization roles, sorted."""
        return sorted((slug, role) for slug, roles in self.org_roles.items() for role in roles)
