"""Guards that run again on the result of a critical change in `live` (contract 3.4).

They also guard `reinstate` and `revert_revision`. The running event may still be
corrected, so `dateInFuture`, `publishAtReached` and `fourEyes` are not part of it.
"""

from __future__ import annotations

from datetime import datetime

from app.modules.pipeline.guards import (
    attachments_scanned,
    flyer_date_confirmed,
    has_field,
    image_or_exception,
    rights_complete,
    title_clean,
    venue_or_text,
)
from app.modules.pipeline.reasons import Reason, blockers, refusal
from app.modules.pipeline.snapshot import Actor, Snapshot

LIVE_GUARDS = (
    has_field("title", "summary", "starts_at", "ends_at", "primary_category_id"),
    venue_or_text,
    image_or_exception,
    rights_complete,
    attachments_scanned,
    title_clean,
    flyer_date_confirmed,
)


def live_reasons(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Run the live guards on the result snapshot and collect their reasons."""
    return [reason for guard in LIVE_GUARDS for reason in guard(snapshot, actor, now)]


def enforce_live(snapshot: Snapshot, actor: Actor, now: datetime) -> None:
    """Raise the 422 problem when a live guard blocks the result snapshot."""
    reasons = live_reasons(snapshot, actor, now)
    if blockers(reasons):
        raise refusal(reasons)
