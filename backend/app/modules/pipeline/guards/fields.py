"""Guards on the plain fields: required fields, venue, date, creation scope and quota."""

from __future__ import annotations

from datetime import datetime

from app.modules.pipeline.guards.common import FIELD_NAMES, Guard
from app.modules.pipeline.reasons import FixAction, Reason, blocker
from app.modules.pipeline.snapshot import Actor, Snapshot

PROPOSAL_QUOTA = 5


def _present(value: object) -> bool:
    return bool(value.strip()) if isinstance(value, str) else value is not None


def has_field(*fields: str) -> Guard:
    """Build the guard `hasField`: every named snapshot field is filled."""

    def guard(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
        return [
            blocker("field_missing", field=FIELD_NAMES[name], fix=FixAction.FILL_FIELD)
            for name in fields
            if not _present(getattr(snapshot, name))
        ]

    return guard


def venue_or_text(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `venueOrText`: a venue or a non-empty free-text venue."""
    if snapshot.venue_id is not None or _present(snapshot.venue_text):
        return []
    return [blocker("venue_missing", field="venueId", fix=FixAction.PICK_VENUE)]


def date_in_future(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `dateInFuture`: the event has not ended yet (a running event passes)."""
    if snapshot.ends_at is not None and snapshot.ends_at > now:
        return []
    return [blocker("start_in_past", field="startsAt", fix=FixAction.CHANGE_DATE)]


def organization_scope_or_proposal(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `organizationScopeOrProposal` of T00.

    A proposal (no organization) needs nothing; a dossier in an organization needs
    `event.create` there, and a refusal looks like a missing organization (404).
    """
    if snapshot.organization_id is None or actor.can("event.create"):
        return []
    return [blocker("organization_scope", field="organizationId")]


def proposal_quota(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `proposalQuota(5)`: a person holds at most five open proposals."""
    if snapshot.organization_id is None and snapshot.open_proposals >= PROPOSAL_QUOTA:
        return [blocker("proposal_quota_exceeded", field="organizationId")]
    return []
