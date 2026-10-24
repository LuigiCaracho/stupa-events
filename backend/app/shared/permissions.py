"""Permission catalogue, role catalogue and the OIDC group grammar.

The roles and their rights are code, not data (PLAN 5.3). The IdP groups are the only
source of a membership, and `group_mapping` rows are the only judge of what a group
means (M2). `parse_group` and `default_mappings` stay as the generator of the proposal
that the admin API applies; they do not take part in the resolution. Every decision runs
through `Principal.has`, never through a role name.

Copied from STUPA-Workflow@93c33d6 backend/app/shared/permissions.py (rewritten for events)
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

PERMISSION_CATALOGUE: tuple[str, ...] = (
    "event.read_all",
    "event.create",
    "event.edit",
    "event.publish",
    "event.cancel",
    "event.restore",
    "dossier.attach",
    "dossier.read_restricted",
    "comment.write",
    "library.read",
    "library.manage",
    "format.manage",
    "series.manage",
    "offer.manage",
    "import.review",
    "import.manage",
    "taxonomy.manage",
    "venue.manage",
    "audit.read",
    "audit.verify",
    "admin.mappings",
    "admin.sessions.revoke",
    "admin.status",
    "digest.release",
    "privacy.erase",
    "subscriber.stats",
)

ORG_ROLES: tuple[str, ...] = ("viewer", "submitter", "organizer")
GLOBAL_ROLES: tuple[str, ...] = ("admin", "editor", "stupa", "member")

_SUBMITTER = frozenset(
    {"event.create", "event.edit", "dossier.attach", "comment.write", "library.read"}
)
_ORGANIZER = _SUBMITTER | {"event.publish", "event.cancel"}
_EDITOR = _ORGANIZER | {
    "event.read_all",
    "event.restore",
    "dossier.read_restricted",
    "library.manage",
    "format.manage",
    "series.manage",
    "offer.manage",
    "import.review",
    "import.manage",
    "taxonomy.manage",
    "venue.manage",
    "digest.release",
    "subscriber.stats",
}

ROLE_PERMISSIONS: Mapping[str, frozenset[str]] = {
    "viewer": frozenset({"library.read"}),
    "submitter": _SUBMITTER,
    "organizer": _ORGANIZER,
    "editor": _EDITOR,
    "stupa": frozenset({"event.read_all", "comment.write", "library.read"}),
    "member": frozenset({"library.read"}),
    "admin": frozenset(
        {
            "audit.read",
            "audit.verify",
            "admin.mappings",
            "admin.sessions.revoke",
            "admin.status",
            "taxonomy.manage",
            "venue.manage",
            "import.manage",
            "digest.release",
            "privacy.erase",
            "subscriber.stats",
        }
    ),
}

RESERVED_GROUP_PREFIX = "events-system:"

GLOBAL_GROUPS: Mapping[str, str] = {
    "events-admin": "admin",
    "events-editor": "editor",
    "events-stupa": "stupa",
}

_ORG_GROUP = re.compile(
    r"^events-(?P<org>[a-z0-9][a-z0-9-]*)-(?P<role>viewer|submitter|organizer)$"
)


@dataclass(frozen=True, slots=True)
class GroupGrant:
    """A role that an IdP group grants, global when `org` is `None`."""

    role: str
    org: str | None = None


def parse_group(name: str) -> GroupGrant | None:
    """Turn an OIDC group name into the grant it expresses.

    Args:
        name: The group name as the IdP emits it.

    Returns:
        The grant, or `None` for a group that is not part of the grammar, including
        every name in the reserved `events-system:` namespace.
    """
    if name.startswith(RESERVED_GROUP_PREFIX):
        return None
    if name in GLOBAL_GROUPS:
        return GroupGrant(role=GLOBAL_GROUPS[name])
    match = _ORG_GROUP.fullmatch(name)
    if match is None:
        return None
    return GroupGrant(role=match["role"], org=match["org"])


def grants_from_groups(groups: Iterable[str]) -> tuple[GroupGrant, ...]:
    """Return the distinct grants of a group set, in a stable order."""
    found = {grant for name in groups if (grant := parse_group(name)) is not None}
    return tuple(sorted(found, key=lambda g: (g.org or "", g.role)))


def permissions_of(roles: Iterable[str]) -> frozenset[str]:
    """Return the union of the permissions of the given roles."""
    return frozenset().union(*(ROLE_PERMISSIONS.get(role, frozenset()) for role in roles))


@dataclass(frozen=True, slots=True)
class DefaultMapping:
    """A proposed `group_mapping` row: an IdP group, its role and its organization slug."""

    group: str
    role: str
    org: str | None = None


def default_mappings(slugs: Iterable[str]) -> tuple[DefaultMapping, ...]:
    """Return the proposed mappings (PLAN 5.6): three global ones and the org roles.

    Args:
        slugs: Slugs of the active organizations.
    """
    global_rows = tuple(DefaultMapping(group, role) for group, role in GLOBAL_GROUPS.items())
    org_rows = tuple(
        DefaultMapping(f"events-{slug}-{role}", role, slug)
        for slug in sorted(slugs)
        for role in ORG_ROLES
    )
    return global_rows + org_rows
