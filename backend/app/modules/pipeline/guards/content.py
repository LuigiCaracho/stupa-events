"""Guards on content: title marks, duplicates, comments, checklist, facts, follow-up.

The guard functions are pure. M4 fills comments and checklist counts from the database
(`dossier.guard_data`), M5 the location, the facts and the follow-up inputs; only the
duplicate score keeps a neutral snapshot value until M6, and a neutral value always means
"satisfied".
"""

from __future__ import annotations

import re
from datetime import datetime

from app.modules.pipeline.guards.common import Guard
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
    """Guard `noOpenCommentOnField(hero)`: no open comment on the poster or its replacements."""
    if snapshot.open_hero_comments > 0:
        return [blocker("open_comment_on_hero", field="poster", fix=FixAction.OPEN_COMMENT)]
    return []


def location_confirmed(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `locationConfirmed`: a free venue text is confirmed as public (M5)."""
    if snapshot.location_confirmed:
        return []
    return [blocker("location_unconfirmed", field="venueId", fix=FixAction.CONFIRM_LOCATION)]


def facts_valid(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `factsValid`: the facts profile of the main category is complete (M5)."""
    if snapshot.facts_error is None:
        return []
    return [blocker("facts_invalid", field=snapshot.facts_error, fix=FixAction.FILL_FACTS)]


def checklist_done_in(phase: str) -> Guard:
    """Build the guard `checklistDone(phase)`: no open required item of that phase.

    The reason carries the phase in `field`. Only `planning` (T02) and `followup` (T09)
    are loaded into the snapshot.
    """
    attribute = {"planning": "open_required_checklist", "followup": "open_required_followup"}[phase]

    def guard(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
        if getattr(snapshot, attribute) > 0:
            return [blocker("checklist_open", field=phase, fix=FixAction.OPEN_CHECKLIST)]
        return []

    guard.__doc__ = f"Guard `checklistDone({phase})`: no open required checklist item."
    return guard


checklist_done = checklist_done_in("planning")
checklist_done_followup = checklist_done_in("followup")


def open_comment_required(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `openCommentRequired` of T03: at least one open root comment (`None` passes)."""
    if snapshot.open_comments == 0:
        return [blocker("open_comment_required", fix=FixAction.OPEN_COMMENT)]
    return []


def retrospective_filled(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `retrospectiveFilled` of T09: a retrospective document with text exists."""
    if snapshot.retrospective_filled:
        return []
    return [blocker("retrospective_missing", fix=FixAction.FILL_RETROSPECTIVE)]


def outcome_set_or_waived(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `outcomeSetOrWaived` of T09: attendance and costs are set, or the waiver is."""
    return [] if snapshot.outcome_set else [blocker("outcome_missing", fix=FixAction.FILL_OUTCOME)]


def howto_verified(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `howtoVerified` of T09: the howto is verified, or there is nothing to verify."""
    return (
        [] if snapshot.howto_verified else [blocker("howto_unverified", fix=FixAction.VERIFY_HOWTO)]
    )
