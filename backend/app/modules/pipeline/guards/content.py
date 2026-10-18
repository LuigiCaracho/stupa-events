"""Guards on content that later milestones fill: title marks, duplicates, comments, facts.

The guard functions are complete; the snapshot carries a neutral value until M4 to M6
provide the data, and a neutral value always means "satisfied".
"""

from __future__ import annotations

import re
from datetime import datetime

from app.modules.pipeline.reasons import FixAction, Reason, blocker
from app.modules.pipeline.snapshot import Actor, Snapshot

DUPLICATE_THRESHOLD = 0.8
_STATUS_IN_TITLE = re.compile(
    r"\[(?:canceled|cancelled|abgesagt|verschoben)\]|!verschoben!|\babgesagt\b", re.IGNORECASE
)


def title_clean(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `titleClean`: no status word in the title while the event is scheduled."""
    if snapshot.public_status == "scheduled" and _STATUS_IN_TITLE.search(snapshot.title or ""):
        return [blocker("title_has_status", field="title", fix=FixAction.MARK_CANCELLATION)]
    return []


def no_open_duplicate(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `noOpenDuplicate`: no unresolved duplicate score of 0.8 or more (M6)."""
    if snapshot.duplicate_score is not None and snapshot.duplicate_score >= DUPLICATE_THRESHOLD:
        return [blocker("duplicate_unresolved", fix=FixAction.REVIEW_DUPLICATE)]
    return []


def no_open_comment_on_hero(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `noOpenCommentOnField(hero)`: no open comment on the poster (M4)."""
    if snapshot.open_hero_comments > 0:
        return [blocker("open_comment_on_hero", field="poster", fix=FixAction.OPEN_COMMENT)]
    return []


def location_confirmed(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `locationConfirmed`: the venue precision is confirmed (M5)."""
    if snapshot.location_confirmed:
        return []
    return [blocker("location_unconfirmed", field="venueId", fix=FixAction.CONFIRM_LOCATION)]


def facts_valid(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `factsValid`: the facts profile of the main category is complete (M4)."""
    if snapshot.facts_error is None:
        return []
    return [blocker("facts_invalid", field=snapshot.facts_error, fix=FixAction.FILL_FACTS)]


def checklist_done(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `checklistDone`: no open required checklist item of the phase (M4)."""
    if snapshot.open_required_checklist > 0:
        return [blocker("checklist_open", fix=FixAction.OPEN_CHECKLIST)]
    return []


def open_comment_required(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `openCommentRequired` of T03; `None` (not tracked before M4) is satisfied."""
    if snapshot.open_comments == 0:
        return [blocker("open_comment_required", fix=FixAction.OPEN_COMMENT)]
    return []


def retrospective_filled(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `retrospectiveFilled` of T09 (M5)."""
    return [] if snapshot.retrospective_filled else [blocker("retrospective_missing")]


def outcome_set_or_waived(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `outcomeSetOrWaived` of T09 (M5)."""
    return [] if snapshot.outcome_set else [blocker("outcome_missing")]


def howto_verified(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `howtoVerified` of T09 (M5)."""
    return [] if snapshot.howto_verified else [blocker("howto_unverified")]
