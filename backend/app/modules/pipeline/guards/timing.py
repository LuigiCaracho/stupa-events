"""Guards on time, origin and people: worker conditions, Four-Eyes and the warnings."""

from __future__ import annotations

from datetime import datetime, timedelta

from app.modules.pipeline.guards.common import Guard, system_only
from app.modules.pipeline.reasons import FixAction, Reason, blocker, warning
from app.modules.pipeline.snapshot import Actor, Snapshot

LONG_RUNNING = timedelta(days=7)


def _publish_at_reached(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `publishAtReached`: the scheduled publication time has come."""
    if snapshot.publish_at is not None and snapshot.publish_at <= now:
        return []
    return [blocker("publish_at_not_reached")]


def _human_approval(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `humanApproval`: a person, never the system, approved the dossier."""
    approver = snapshot.approved_by
    if approver is not None and not approver.startswith("system:"):
        return []
    return [blocker("not_human_approved")]


publish_at_reached = system_only(_publish_at_reached)
human_approval = system_only(_human_approval)


def ended_more_than(hours: int) -> Guard:
    """Build the guard `endedMoreThan(hours)`: the event ended at least `hours` ago."""

    def guard(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
        if snapshot.ends_at is not None and snapshot.ends_at + timedelta(hours=hours) <= now:
            return []
        return [blocker("not_ended_yet")]

    return guard


def origin_is(*kinds: str) -> Guard:
    """Build the guard `originIs(...)`: the dossier comes from one of the origins."""

    def guard(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
        return [] if snapshot.origin_kind in kinds else [blocker("origin_kind_mismatch")]

    return guard


def followup_older_than(days: int) -> Guard:
    """Build the guard `followupOlderThan(days)`: the dossier waited long enough."""

    def guard(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
        entered = snapshot.entered_followup_at
        if entered is not None and entered + timedelta(days=days) <= now:
            return []
        return [blocker("followup_not_due")]

    return guard


def four_eyes(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `fourEyes`: the approving person did not submit (E06).

    It binds organization approvers and admins always, editors only with
    `EDITOR_FOUR_EYES`. A dossier without a submitter blocks too.
    """
    if not actor.four_eyes:
        return []
    if snapshot.submitted_by is None or snapshot.submitted_by == actor.sub:
        return [blocker("four_eyes")]
    return []


def wall_clock_ok(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Warning `wallClockOk`: the start falls into the gap or the repeated hour (M6)."""
    match snapshot.ambiguous_wall_clock:
        case "ambiguous":
            return [warning("time_ambiguous", field="startsAt", fix=FixAction.CONFIRM_TIME)]
        case "gap":
            return [warning("time_gap", field="startsAt", fix=FixAction.CONFIRM_TIME)]
        case _:
            return []


def end_estimated(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Warning: the end was missing and is estimated as start plus two hours."""
    if snapshot.end_estimated:
        return [warning("end_estimated", field="endsAt", fix=FixAction.SET_END)]
    return []


def long_running(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Warning: the event lasts longer than seven days; an offer fits better."""
    if (
        snapshot.starts_at
        and snapshot.ends_at
        and snapshot.ends_at - snapshot.starts_at > LONG_RUNNING
    ):
        return [warning("long_running", field="endsAt", fix=FixAction.MAKE_OFFER)]
    return []
