"""Immutable view of a dossier that the guards read, and the actor that fires.

Guards are pure functions of `(snapshot, actor, now)`. The service builds the snapshot
from the rows and the actor from the principal, so a guard never touches the database
or the session. Fields that later milestones fill (duplicates, comments, checklists,
facts, follow-up data) carry a neutral default that every guard reports as satisfied.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

type ActorKind = Literal["org", "editor", "admin", "system"]

SYSTEM_SUB = "system:advance_states"


@dataclass(frozen=True, slots=True)
class PosterSnapshot:
    """The facts about the current poster that the media guards check."""

    scan_status: str
    has_derivatives: bool
    alt_text: str | None
    credit: str | None
    rights_basis: str
    persons_depicted: bool = False
    consent_note: str | None = None
    created_at: datetime | None = None
    reused_in_other_year: bool = False

    @property
    def usable_media(self) -> bool:
        """Tell if the poster file itself is ready: scanned clean and derived."""
        return self.scan_status == "clean" and self.has_derivatives

    @property
    def missing_rights(self) -> tuple[str, ...]:
        """Name the rights fields still open: alt text, credit, basis, consent note."""
        missing = []
        if not (self.alt_text or "").strip():
            missing.append("altText")
        if not (self.credit or "").strip():
            missing.append("credit")
        if self.rights_basis == "unknown":
            missing.append("rightsBasis")
        if not self.consent_ok:
            missing.append("consentNote")
        return tuple(missing)

    @property
    def usable(self) -> bool:
        """Mirror of the SQL function `attachment_poster_ok`: file ready and rights set."""
        return self.usable_media and not self.missing_rights

    @property
    def consent_ok(self) -> bool:
        """Tell if depicted persons are covered by a consent note (or nobody is depicted)."""
        return not self.persons_depicted or bool((self.consent_note or "").strip())


@dataclass(frozen=True, slots=True)
class Snapshot:
    """The fields of a dossier that guards, transitions and field rules read."""

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
    description_md: str | None = None
    venue_id: UUID | None = None
    ticket_url: str | None = None
    website_url: str | None = None
    cost_text: str | None = None
    publish_at: datetime | None = None
    public_status: str = "scheduled"
    end_estimated: bool = False
    flyer_checked_at: datetime | None = None
    approved_by: str | None = None
    origin_kind: str = "internal"
    rev: int = 1
    published_rev: int | None = None
    text_reviewed_rev: int = 0
    quarantined_attachments: int = 0
    duplicate_score: float | None = None
    open_hero_comments: int = 0
    open_required_checklist: int = 0
    facts_error: str | None = None
    open_proposals: int = 0
    entered_followup_at: datetime | None = None
    ambiguous_wall_clock: str | None = None
    location_confirmed: bool = True
    open_comments: int | None = None
    retrospective_filled: bool = True
    outcome_set: bool = True
    howto_verified: bool = True


@dataclass(frozen=True, slots=True)
class Actor:
    """Who fires: the sub, the permissions held in the dossier's organization and the kind."""

    sub: str
    permissions: frozenset[str]
    kind: ActorKind = "org"
    four_eyes: bool = True

    def can(self, permission: str) -> bool:
        """Tell if the actor holds `permission` in the organization of the dossier."""
        return permission in self.permissions


SYSTEM_ACTOR = Actor(SYSTEM_SUB, frozenset(), kind="system", four_eyes=False)
