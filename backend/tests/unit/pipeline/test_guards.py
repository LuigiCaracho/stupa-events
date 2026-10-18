"""Guards as pure functions: reasons, order, codes (U-GUARD truth table of M1)."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.pipeline import guards
from app.modules.pipeline.reasons import FixAction, Severity, blockers
from app.modules.pipeline.snapshot import PosterSnapshot
from tests.unit.pipeline.support import NOW, actor, snap


def test_has_field_names_each_missing_field_in_camel_case() -> None:
    guard = guards.has_field("title", "starts_at", "primary_category_id", "venue_text")
    reasons = guard(
        snap(title="  ", starts_at=None, primary_category_id=None, venue_text=""),
        actor("organizer"),
        NOW,
    )
    assert [(r.code, r.field) for r in reasons] == [
        ("field_missing", "title"),
        ("field_missing", "startsAt"),
        ("field_missing", "primaryCategoryId"),
        ("field_missing", "venueText"),
    ]
    assert all(
        r.fix_action is FixAction.FILL_FIELD and r.severity is Severity.BLOCKER for r in reasons
    )
    assert reasons[0].message_key == "guards.field_missing"


def test_has_field_passes_with_all_fields() -> None:
    assert guards.has_field("title", "summary")(snap(), actor("organizer"), NOW) == []


@pytest.mark.parametrize(
    ("ends_in", "ok"),
    [
        (timedelta(hours=1), True),
        (timedelta(seconds=1), True),
        (timedelta(0), False),
        (-timedelta(hours=1), False),
    ],
)
def test_date_in_future_lets_a_running_event_pass(ends_in: timedelta, ok: bool) -> None:
    snapshot = snap(starts_at=NOW - timedelta(hours=2), ends_at=NOW + ends_in)
    reasons = guards.date_in_future(snapshot, actor("organizer"), NOW)
    assert (reasons == []) is ok
    if not ok:
        assert reasons[0].code == "start_in_past" and reasons[0].fix_action is FixAction.CHANGE_DATE


def test_date_in_future_without_end_fails() -> None:
    assert (
        guards.date_in_future(snap(ends_at=None), actor("organizer"), NOW)[0].code
        == "start_in_past"
    )


@pytest.mark.parametrize(
    "poster",
    [
        None,
        PosterSnapshot("pending", True, "Alt", "Credit", "own_work"),
        PosterSnapshot("infected", True, "Alt", "Credit", "own_work"),
        PosterSnapshot("clean", False, "Alt", "Credit", "own_work"),
        PosterSnapshot("clean", True, " ", "Credit", "own_work"),
        PosterSnapshot("clean", True, "Alt", None, "own_work"),
        PosterSnapshot("clean", True, "Alt", "Credit", "unknown"),
    ],
)
def test_image_required_for_every_unusable_poster(poster: PosterSnapshot | None) -> None:
    reasons = guards.image_or_exception(snap(poster=poster), actor("editor"), NOW)
    assert [(r.code, r.field, r.fix_action) for r in reasons] == [
        ("image_required", "poster", FixAction.UPLOAD_POSTER)
    ]


def test_image_passes_with_poster_or_exception() -> None:
    assert guards.image_or_exception(snap(), actor("editor"), NOW) == []
    no_poster = snap(poster=None, image_exception_reason="Hochschulveranstaltung")
    assert guards.image_or_exception(no_poster, actor("editor"), NOW) == []


def test_organization_scope_guard() -> None:
    assert guards.organization_scope_or_proposal(snap(), actor("submitter"), NOW) == []
    assert (
        guards.organization_scope_or_proposal(snap(organization_id=None), actor("member"), NOW)
        == []
    )
    outside = guards.organization_scope_or_proposal(snap(), actor("viewer"), NOW)
    assert outside[0].code == "organization_scope"


def test_blockers_filters_warnings() -> None:
    reasons = guards.date_in_future(snap(ends_at=NOW), actor("organizer"), NOW)
    warning = replace(reasons[0], severity=Severity.WARNING)
    assert blockers([warning, *reasons]) == reasons
