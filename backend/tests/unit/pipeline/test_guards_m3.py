"""One positive and one negative case for every guard code of the M3 table (2.3)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.pipeline import guards
from app.modules.pipeline.reasons import FixAction, Severity
from app.modules.pipeline.snapshot import PosterSnapshot
from tests.unit.pipeline.support import GOOD_POSTER, NOW, actor, snap

ORGANIZER = actor("organizer", sub="o")
SYSTEM = actor("system")


def only(reasons: list) -> tuple[str, FixAction | None, Severity]:
    assert len(reasons) == 1
    return reasons[0].code, reasons[0].fix_action, reasons[0].severity


def test_venue_missing_needs_neither_venue_id_nor_text() -> None:
    assert guards.venue_or_text(snap(), ORGANIZER, NOW) == []
    from uuid import uuid4

    assert guards.venue_or_text(snap(venue_text=None, venue_id=uuid4()), ORGANIZER, NOW) == []
    got = guards.venue_or_text(snap(venue_text="  ", venue_id=None), ORGANIZER, NOW)
    assert only(got) == ("venue_missing", FixAction.PICK_VENUE, Severity.BLOCKER)


def test_rights_incomplete_only_when_a_poster_counts() -> None:
    depicted = replace(GOOD_POSTER, persons_depicted=True, consent_note=" ")
    got = guards.rights_complete(snap(poster=depicted), ORGANIZER, NOW)
    assert only(got) == ("rights_incomplete", FixAction.FILL_RIGHTS, Severity.BLOCKER)
    consent = replace(depicted, consent_note="Einwilligung liegt vor")
    assert guards.rights_complete(snap(poster=consent), ORGANIZER, NOW) == []
    excepted = snap(poster=depicted, image_exception_reason="Hochschulveranstaltung")
    assert guards.rights_complete(excepted, ORGANIZER, NOW) == []
    assert guards.rights_complete(snap(poster=None), ORGANIZER, NOW) == []


def test_attachment_quarantined() -> None:
    assert guards.attachments_scanned(snap(), ORGANIZER, NOW) == []
    got = guards.attachments_scanned(snap(quarantined_attachments=1), ORGANIZER, NOW)
    assert only(got)[0] == "attachment_quarantined"


@pytest.mark.parametrize(
    ("score", "blocks"), [(None, False), (0.79, False), (0.8, True), (0.9, True)]
)
def test_duplicate_unresolved(score: float | None, blocks: bool) -> None:
    got = guards.no_open_duplicate(snap(duplicate_score=score), ORGANIZER, NOW)
    assert bool(got) is blocks
    if blocks:
        assert only(got) == ("duplicate_unresolved", FixAction.REVIEW_DUPLICATE, Severity.BLOCKER)


@pytest.mark.parametrize(
    "title",
    [
        "[ABGESAGT] Movienight",
        "Kino [cancelled]",
        "Party [Verschoben]",
        "!VERSCHOBEN! Quiz",
        "Heute abgesagt",
    ],
)
def test_title_has_status_matches_the_marks(title: str) -> None:
    got = guards.title_clean(snap(title=title), ORGANIZER, NOW)
    assert only(got) == ("title_has_status", FixAction.MARK_CANCELLATION, Severity.BLOCKER)


def test_title_clean_passes_plain_and_cancelled_events() -> None:
    assert guards.title_clean(snap(title="Movienight"), ORGANIZER, NOW) == []
    assert guards.title_clean(snap(title="Die Abgesagten"), ORGANIZER, NOW) == []
    cancelled = snap(title="[ABGESAGT] Movienight", public_status="cancelled")
    assert guards.title_clean(cancelled, ORGANIZER, NOW) == []


def test_open_comment_on_hero() -> None:
    assert guards.no_open_comment_on_hero(snap(), ORGANIZER, NOW) == []
    got = guards.no_open_comment_on_hero(snap(open_hero_comments=2), ORGANIZER, NOW)
    assert only(got) == ("open_comment_on_hero", FixAction.OPEN_COMMENT, Severity.BLOCKER)


def test_flyer_date_needs_a_check_after_the_upload() -> None:
    reused = replace(GOOD_POSTER, reused_in_other_year=True, created_at=NOW)
    got = guards.flyer_date_confirmed(snap(poster=reused), ORGANIZER, NOW)
    assert only(got) == ("flyer_date", FixAction.CONFIRM_FLYER, Severity.BLOCKER)
    stale = snap(poster=reused, flyer_checked_at=NOW - timedelta(hours=1))
    assert guards.flyer_date_confirmed(stale, ORGANIZER, NOW)
    fresh = snap(poster=reused, flyer_checked_at=NOW)
    assert guards.flyer_date_confirmed(fresh, ORGANIZER, NOW) == []
    assert guards.flyer_date_confirmed(snap(poster=None), ORGANIZER, NOW) == []
    assert guards.flyer_date_confirmed(snap(), ORGANIZER, NOW) == []
    no_stamp = replace(GOOD_POSTER, reused_in_other_year=True)
    assert guards.flyer_date_confirmed(snap(poster=no_stamp, flyer_checked_at=NOW), ORGANIZER, NOW)


def test_location_unconfirmed() -> None:
    assert guards.location_confirmed(snap(), ORGANIZER, NOW) == []
    got = guards.location_confirmed(snap(location_confirmed=False), ORGANIZER, NOW)
    assert only(got) == ("location_unconfirmed", FixAction.CONFIRM_LOCATION, Severity.BLOCKER)


def test_facts_invalid() -> None:
    assert guards.facts_valid(snap(), ORGANIZER, NOW) == []
    got = guards.facts_valid(snap(facts_error="ageLimit"), ORGANIZER, NOW)
    assert only(got) == ("facts_invalid", FixAction.FILL_FACTS, Severity.BLOCKER)
    assert got[0].field == "ageLimit"


def test_checklist_open() -> None:
    assert guards.checklist_done(snap(), ORGANIZER, NOW) == []
    got = guards.checklist_done(snap(open_required_checklist=3), ORGANIZER, NOW)
    assert only(got) == ("checklist_open", FixAction.OPEN_CHECKLIST, Severity.BLOCKER)


def test_open_comment_required_is_satisfied_while_untracked() -> None:
    assert guards.open_comment_required(snap(), ORGANIZER, NOW) == []
    assert guards.open_comment_required(snap(open_comments=2), ORGANIZER, NOW) == []
    got = guards.open_comment_required(snap(open_comments=0), ORGANIZER, NOW)
    assert only(got)[0] == "open_comment_required"


@pytest.mark.parametrize(
    ("guard", "field", "code"),
    [
        (guards.retrospective_filled, "retrospective_filled", "retrospective_missing"),
        (guards.outcome_set_or_waived, "outcome_set", "outcome_missing"),
        (guards.howto_verified, "howto_verified", "howto_unverified"),
    ],
)
def test_followup_guards(guard, field: str, code: str) -> None:  # noqa: ANN001
    assert guard(snap(), ORGANIZER, NOW) == []
    assert only(guard(snap(**{field: False}), ORGANIZER, NOW))[0] == code


def test_publish_at_reached_binds_the_worker_only() -> None:
    later = snap(publish_at=NOW + timedelta(minutes=1))
    assert guards.publish_at_reached(later, ORGANIZER, NOW) == []
    assert only(guards.publish_at_reached(later, SYSTEM, NOW))[0] == "publish_at_not_reached"
    assert guards.publish_at_reached(snap(publish_at=NOW), SYSTEM, NOW) == []
    assert guards.publish_at_reached(snap(publish_at=None), SYSTEM, NOW)


def test_human_approval_binds_the_worker_only() -> None:
    assert guards.human_approval(snap(approved_by="person"), SYSTEM, NOW) == []
    for approver in (None, "system:advance_states", "system:import"):
        assert only(guards.human_approval(snap(approved_by=approver), SYSTEM, NOW))[0] == (
            "not_human_approved"
        )
    assert guards.human_approval(snap(approved_by=None), ORGANIZER, NOW) == []


@pytest.mark.parametrize(
    ("ended_ago", "ok"),
    [
        (timedelta(hours=12, minutes=1), True),
        (timedelta(hours=12), True),
        (timedelta(hours=11, minutes=59), False),
    ],
)
def test_ended_more_than_twelve_hours(ended_ago: timedelta, ok: bool) -> None:
    snapshot = snap(starts_at=NOW - ended_ago - timedelta(hours=2), ends_at=NOW - ended_ago)
    got = guards.ended_more_than(12)(snapshot, SYSTEM, NOW)
    assert (got == []) is ok
    assert ok or only(got)[0] == "not_ended_yet"
    assert guards.ended_more_than(12)(snap(ends_at=None), SYSTEM, NOW)


def test_origin_is() -> None:
    guard = guards.origin_is("imported", "legacy")
    assert guard(snap(origin_kind="legacy"), SYSTEM, NOW) == []
    assert only(guard(snap(origin_kind="internal"), SYSTEM, NOW))[0] == "origin_kind_mismatch"


@pytest.mark.parametrize(("days", "ok"), [(29, False), (30, True), (31, True)])
def test_followup_older_than_thirty_days(days: int, ok: bool) -> None:
    snapshot = snap(entered_followup_at=NOW - timedelta(days=days))
    got = guards.followup_older_than(30)(snapshot, SYSTEM, NOW)
    assert (got == []) is ok
    assert guards.followup_older_than(30)(snap(entered_followup_at=None), SYSTEM, NOW)


def test_four_eyes_rule() -> None:
    mine = snap(submitted_by="me")
    approver = actor("approver", sub="me")
    got = guards.four_eyes(mine, approver, NOW)
    assert only(got) == ("four_eyes", None, Severity.BLOCKER)
    assert guards.four_eyes(mine, actor("approver", sub="you"), NOW) == []
    assert guards.four_eyes(snap(submitted_by=None), approver, NOW)
    assert guards.four_eyes(mine, actor("editor", sub="me"), NOW) == []
    bound = actor("editor", sub="me", editor_four_eyes=True)
    assert guards.four_eyes(mine, bound, NOW)
    assert guards.four_eyes(mine, actor("admin", sub="me"), NOW)


def test_warnings_never_block() -> None:
    cases = [
        (guards.end_estimated, snap(end_estimated=True), "end_estimated", FixAction.SET_END),
        (
            guards.long_running,
            snap(ends_at=NOW + timedelta(days=11)),
            "long_running",
            FixAction.MAKE_OFFER,
        ),
        (
            guards.wall_clock_ok,
            snap(ambiguous_wall_clock="ambiguous"),
            "time_ambiguous",
            FixAction.CONFIRM_TIME,
        ),
        (
            guards.wall_clock_ok,
            snap(ambiguous_wall_clock="gap"),
            "time_gap",
            FixAction.CONFIRM_TIME,
        ),
    ]
    for guard, snapshot, code, fix in cases:
        assert only(guard(snapshot, ORGANIZER, NOW)) == (code, fix, Severity.WARNING)
        assert guard(snap(), ORGANIZER, NOW) == []
    assert guards.long_running(snap(starts_at=None), ORGANIZER, NOW) == []


def test_proposal_quota() -> None:
    proposal = snap(organization_id=None, open_proposals=guards.PROPOSAL_QUOTA - 1)
    assert guards.proposal_quota(proposal, ORGANIZER, NOW) == []
    full = replace(proposal, open_proposals=guards.PROPOSAL_QUOTA)
    assert only(guards.proposal_quota(full, ORGANIZER, NOW))[0] == "proposal_quota_exceeded"
    assert (
        guards.proposal_quota(replace(full, organization_id=snap().organization_id), ORGANIZER, NOW)
        == []
    )


def test_system_only_wrapper_keeps_the_doc_and_skips_humans() -> None:
    wrapped = guards.system_only(guards.date_in_future)
    past = snap(ends_at=NOW - timedelta(hours=1))
    assert wrapped(past, ORGANIZER, NOW) == []
    assert wrapped(past, SYSTEM, NOW)
    assert wrapped.__doc__ == guards.date_in_future.__doc__


def test_pending_or_infected_posters_are_not_usable() -> None:
    for status in ("pending", "infected", "error"):
        poster = PosterSnapshot(status, True, "a", "c", "own_work")
        assert only(guards.image_or_exception(snap(poster=poster), ORGANIZER, NOW))[0] == (
            "image_required"
        )
