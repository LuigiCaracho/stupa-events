"""RBAC resolution: turn a `principal` row into a `Principal` with roles and permissions.

The IdP groups are the only source of a membership, and the rows of `group_mapping`
(migration `0002_events_core`) are the only judge of what a group means (M2, D1). The
group name carries no meaning in code. `effective_grants` is the one function that
computes the roles of a group set; the resolver and `membership_sync` both call it. The
reserved namespace `events-system:` never enters the group set. A `submitter` or
`organizer` role gives rights in its organization only. The bootstrap admin lists grant the
global `admin` role. A mapping to an inactive organization
grants nothing; the sync drops its memberships when `active` flips.

The tables are read through lightweight table constructs, so this module needs no
model of the events schema.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/auth/rbac.py (group set cleaning)
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import Boolean, Uuid, or_, select
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
    permissions_of,
)

_GROUP_MAPPING = table(
    "group_mapping",
    column("oidc_group", SaText),
    column("role", SaText),
    column("organization_id", Uuid),
)
_ORGANIZATION = table(
    "organization",
    column("id", Uuid),
    column("slug", SaText),
    column("active", Boolean),
)

MappingRow = tuple[str, UUID | None, str | None, str]
MappingRows = Sequence[MappingRow]


@dataclass(frozen=True, slots=True)
class EffectiveGrants:
    """The roles a group set grants."""

    global_roles: frozenset[str] = frozenset()
    org_roles: dict[str, frozenset[str]] = field(default_factory=dict)
    org_ids: dict[str, UUID] = field(default_factory=dict)


def clean_groups(raw: Iterable[object] | None) -> set[str]:
    """Return the group claim without the reserved `events-system:` namespace."""
    return {g for g in (str(item) for item in raw or []) if not g.startswith(RESERVED_GROUP_PREFIX)}


async def load_mappings(db: AsyncSession, groups: Collection[str] | None = None) -> MappingRows:
    """Read `group_mapping` rows (all, or those of `groups`) joined to their organization.

    Rows of an inactive organization are dropped.
    """
    query = (
        select(
            _GROUP_MAPPING.c.role,
            _ORGANIZATION.c.id,
            _ORGANIZATION.c.slug,
            _GROUP_MAPPING.c.oidc_group,
        )
        .select_from(
            _GROUP_MAPPING.outerjoin(
                _ORGANIZATION, _ORGANIZATION.c.id == _GROUP_MAPPING.c.organization_id
            )
        )
        .where(or_(_GROUP_MAPPING.c.organization_id.is_(None), _ORGANIZATION.c.active.is_(True)))
    )
    if groups is not None:
        query = query.where(_GROUP_MAPPING.c.oidc_group.in_(groups))
    result = await db.execute(query)
    return [(role, org_id, slug, group) for role, org_id, slug, group in result.all()]


async def effective_grants(db: AsyncSession, groups: Iterable[str]) -> EffectiveGrants:
    """Compute the effective roles of an IdP group set from `group_mapping`.

    A row counts when its role matches its scope: a global role without organization, an
    organization role with one. No group, no query.
    """
    cleaned = clean_groups(groups)
    if not cleaned:
        return EffectiveGrants()
    return grants_from(await load_mappings(db, cleaned), cleaned)


def grants_from(mappings: MappingRows, groups: Iterable[str]) -> EffectiveGrants:
    """Compute the effective roles of a group set from already loaded mapping rows."""
    cleaned = clean_groups(groups)
    rows = [row for row in mappings if row[3] in cleaned]
    global_roles: set[str] = set()
    org_roles: dict[str, set[str]] = {}
    org_ids: dict[str, UUID] = {}
    for role, org_id, slug, _ in rows:
        if slug is None and role in GLOBAL_ROLES:
            global_roles.add(role)
        elif slug is not None and org_id is not None and role in ORG_ROLES:
            org_roles.setdefault(slug, set()).add(role)
            org_ids[slug] = org_id
    return EffectiveGrants(
        frozenset(global_roles),
        {slug: frozenset(roles) for slug, roles in org_roles.items()},
        org_ids,
    )


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
        keyed by organization slug, already bound to the organization ids.
    """
    groups = clean_groups(row.oidc_groups)
    grants = await effective_grants(db, groups)
    global_roles = {"member"} | grants.global_roles
    if _is_bootstrap_admin(row, settings):
        global_roles.add("admin")
    principal = Principal(
        sub=row.sub,
        email=row.email,
        display_name=row.display_name,
        roles=sorted(global_roles),
        permissions=set(permissions_of(global_roles)),
        groups=groups,
        org_roles=dict(grants.org_roles),
    )
    principal.bind_org_ids({slug: org_id for slug, org_id in grants.org_ids.items()})
    return principal
