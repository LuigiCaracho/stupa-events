"""Immutable view of a dossier that the guards read, and the actor that fires.

Guards are pure functions of `(snapshot, actor, now)`. The service builds the snapshot
from the rows and the actor from the principal, so a guard never touches the database
or the session.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.auth.principal import Principal
from app.shared.permissions import PERMISSION_CATALOGUE


@dataclass(frozen=True, slots=True)
class PosterSnapshot:
    """The facts about the current poster that `image_required` checks."""

    scan_status: str
    has_derivatives: bool
    alt_text: str | None
    credit: str | None
    rights_basis: str

    @property
    def usable(self) -> bool:
        """Tell if the poster counts as the required image (scanned, derived, rights set)."""
        return (
            self.scan_status == "clean"
            and self.has_derivatives
            and bool((self.alt_text or "").strip())
            and bool((self.credit or "").strip())
            and self.rights_basis != "unknown"
        )


@dataclass(frozen=True, slots=True)
class Snapshot:
    """The fields of a dossier that guards and transitions read."""

    state: str
    title: str | None
    summary: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    organization_id: UUID | None
    primary_category_id: UUID | None
    venue_text: str | None
    created_by: str | None
    submitted_by: str | None
    poster: PosterSnapshot | None
    image_exception_reason: str | None


@dataclass(frozen=True, slots=True)
class Actor:
    """Who fires: the sub and the permissions held in the organization of the dossier."""

    sub: str
    permissions: frozenset[str]

    def can(self, permission: str) -> bool:
        """Tell if the actor holds `permission` in the organization of the dossier."""
        return permission in self.permissions


def actor_of(principal: Principal, org_id: UUID | None) -> Actor:
    """Build the actor of a principal for the organization `org_id`.

    The principal must have bound its organization ids (`orgs.scope.bind`).
    """
    return Actor(
        sub=principal.sub,
        permissions=frozenset(p for p in PERMISSION_CATALOGUE if principal.has(p, org_id)),
    )
