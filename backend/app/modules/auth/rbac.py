"""RBAC resolution: turn a `principal` row into a `Principal` with roles and permissions.

The IdP groups are the only source of a membership. `parse_group` reads the group
grammar, and a row of `group_mapping` (migration `0002_events_core`) adds a grant that a
name does not express. The reserved namespace `events-system:` never enters the group
set. A `submitter` or `approver` role gives rights in its organization only. The role
`approver` counts only while the organization is `trusted`; otherwise it falls back to
`organizer`. The bootstrap admin lists grant the global `admin` role.

The tables are read through lightweight table constructs, so this module needs no
model of the events schema.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/rbac.py (group grammar)
"""

from __future__ import annotations

from sqlalchemy import Boolean, Uuid, select
from sqlalchemy import Text as SaText
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import column, table

from app.modules.auth.models import Principal as PrincipalRow
from app.modules.auth.principal import Principal
from app.settings import Settings
from app.shared.permissions import (
    GLOBAL_ROLES,
    ORG_ROLES,
    RESERVED_GROUP_PREFIX,
    GroupGrant,
    grants_from_groups,
    permissions_of,
)

_GROUP_MAPPING = table(
    "group_mapping",
    column("oidc_group", SaText),
    column("role", SaText),
    column("organization_id", Uuid),
)
_ORGANIZATION = table(
    "organization", column("id", Uuid), column("slug", SaText), column("trusted", Boolean)
)


def clean_groups(raw: list | None) -> set[str]:
    """Return the group claim without the reserved `events-system:` namespace."""
    return {g for g in (str(item) for item in raw or []) if not g.startswith(RESERVED_GROUP_PREFIX)}


async def _mapped_grants(db: AsyncSession, groups: set[str]) -> list[GroupGrant]:
    """Read the grants of the `group_mapping` rows that match the groups."""
    if not groups:
        return []
    rows = (
        await db.execute(
            select(_GROUP_MAPPING.c.role, _ORGANIZATION.c.slug)
            .select_from(
                _GROUP_MAPPING.outerjoin(
                    _ORGANIZATION, _ORGANIZATION.c.id == _GROUP_MAPPING.c.organization_id
                )
            )
            .where(_GROUP_MAPPING.c.oidc_group.in_(groups))
        )
    ).all()
    return [
        GroupGrant(role=role, org=slug)
        for role, slug in rows
        if (slug is None and role in GLOBAL_ROLES) or (slug is not None and role in ORG_ROLES)
    ]


async def _untrusted(db: AsyncSession, slugs: set[str]) -> set[str]:
    """Return the slugs among `slugs` whose organization is not `trusted`."""
    if not slugs:
        return set()
    trusted = set(
        (
            await db.execute(
                select(_ORGANIZATION.c.slug).where(
                    _ORGANIZATION.c.slug.in_(slugs), _ORGANIZATION.c.trusted.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    return slugs - trusted


def _is_bootstrap_admin(row: PrincipalRow, settings: Settings) -> bool:
    """Tell if the stored bootstrap flag still matches the configured lists."""
    if not row.bootstrap_admin:
        return False
    listed = row.sub in settings.bootstrap_admin_subject_set
    return listed or bool(row.email and row.email.lower() in settings.bootstrap_admin_email_set)


async def resolve_principal(db: AsyncSession, row: PrincipalRow, settings: Settings) -> Principal:
    """Resolve a `principal` row into a full `Principal`.

    Returns:
        The principal with its global roles and permissions and its organization roles
        keyed by organization slug.
    """
    groups = clean_groups(row.oidc_groups)
    grants = [*grants_from_groups(groups), *await _mapped_grants(db, groups)]
    approver_slugs = {g.org for g in grants if g.role == "approver" and g.org}
    untrusted = await _untrusted(db, approver_slugs)

    global_roles = {"member"} | {g.role for g in grants if g.org is None}
    if _is_bootstrap_admin(row, settings):
        global_roles.add("admin")
    org_roles: dict[str, set[str]] = {}
    for grant in grants:
        if grant.org is None:
            continue
        role = "organizer" if grant.role == "approver" and grant.org in untrusted else grant.role
        org_roles.setdefault(grant.org, set()).add(role)

    return Principal(
        sub=row.sub,
        email=row.email,
        display_name=row.display_name,
        roles=sorted(global_roles),
        permissions=set(permissions_of(global_roles)),
        groups=groups,
        org_roles={slug: frozenset(roles) for slug, roles in org_roles.items()},
    )
