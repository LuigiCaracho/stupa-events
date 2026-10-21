"""Validation of a group mapping: a pure function over role and organization.

The database CHECKs of `0002_events_core` are the second net. The checks here give the
admin a precise code per case (contract M2, 2.4).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.shared.permissions import GLOBAL_ROLES, ORG_ROLES, RESERVED_GROUP_PREFIX


@dataclass(frozen=True, slots=True)
class MappingIssue:
    """One refused rule: the stable `code`, the offending `field` and an English text."""

    code: str
    field: str
    msg: str


@dataclass(frozen=True, slots=True)
class OrgFacts:
    """What the validator needs to know about the organization of a mapping."""

    active: bool


def validate_mapping(
    role: str, organization_id: UUID | None, organization: OrgFacts | None
) -> list[MappingIssue]:
    """Return the issues of a `(role, organization)` pair; empty when the pair is valid.

    Args:
        role: The role of the mapping.
        organization_id: The id the caller sent, or `None`.
        organization: The facts of the organization with that id, `None` when it does not
            exist.
    """
    if role == "member":
        return [MappingIssue("implicit_role", "role", "Every signed-in person holds member.")]
    if role in GLOBAL_ROLES:
        if organization_id is None:
            return []
        return [
            MappingIssue("organization_forbidden", "organizationId", "A global role has no scope.")
        ]
    if role not in ORG_ROLES:
        return [MappingIssue("unknown_role", "role", "Unknown role.")]
    if organization_id is None:
        return [
            MappingIssue("organization_required", "organizationId", "An org role needs an org.")
        ]
    if organization is None or not organization.active:
        return [MappingIssue("unknown_organization", "organizationId", "Organization not found.")]
    return []


def validate_group(oidc_group: str) -> list[MappingIssue]:
    """Return the issue of a group name in the reserved namespace, else an empty list."""
    if oidc_group.startswith(RESERVED_GROUP_PREFIX):
        return [
            MappingIssue(
                "reserved_group_prefix", "oidcGroup", "The prefix events-system: is reserved."
            )
        ]
    return []
