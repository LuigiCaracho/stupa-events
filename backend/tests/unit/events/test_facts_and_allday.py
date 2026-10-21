"""Facts profiles, the all-day rule and the location guard (pure functions)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.dossier.guard_data import GuardData
from app.modules.events import allday, facts
from app.modules.events.access import (
    location_is_confirmed,
    outcome_is_set,
    snapshot_of,
    snapshot_with,
)
from app.modules.events.models import Event
from app.modules.pipeline import guards
from app.modules.pipeline.snapshot import Snapshot
from app.shared.errors import ValidationProblem
from tests.unit.events.test_access_and_revisions import event
from tests.unit.pipeline.support import NOW, actor, snap


def test_facts_profiles_accept_their_keys_and_refuse_the_others() -> None:
    assert facts.parse("party", {"ageLimit": 16, "capacity": 80, "securityPlanDone": True}) == {
        "ageLimit": 16,
        "capacity": 80,
        "securityPlanDone": True,
    }
    assert facts.parse("generic", {"budgetCents": 1000, "capacity": None}) == {"budgetCents": 1000}
    assert facts.parse("meeting", {"agendaMd": "# TOPs", "quorumNeeded": 5, "protocolOwner": "x"})
    parsed = facts.parse(
        "trip", {"signupUrl": "https://a.example/x", "signupDeadline": "2026-11-01T10:00:00Z"}
    )
    assert parsed["signupDeadline"].startswith("2026-11-01")
    for profile, bad in (
        ("party", {"ageLimit": 17}),
        ("party", {"agendaMd": "x"}),
        ("generic", {"capacity": -1}),
        ("trip", {"signupUrl": "http://insecure.example"}),
        ("meeting", {"unknown": 1}),
    ):
        with pytest.raises(ValidationError):
            facts.parse(profile, bad)


def test_the_only_blockers_are_a_missing_age_limit_and_min_above_max() -> None:
    assert facts.error_for("party", {}) == "facts.ageLimit"
    assert facts.error_for("party", {"ageLimit": 0}) is None
    assert facts.error_for("party", None) == "facts.ageLimit"
    assert (
        facts.error_for("trip", {"minParticipants": 9, "maxParticipants": 4})
        == "facts.minParticipants"
    )
    assert facts.error_for("trip", {"minParticipants": 4, "maxParticipants": 4}) is None
    assert facts.error_for("trip", {"minParticipants": 4}) is None
    assert facts.error_for("generic", {}) is None and facts.error_for("meeting", {}) is None


def test_fit_keeps_known_keys_and_names_the_dropped_ones() -> None:
    kept, dropped = facts.fit("generic", {"capacity": 5, "ageLimit": 18, "budgetCents": 1})
    assert kept == {"capacity": 5, "budgetCents": 1} and dropped == ["ageLimit"]
    assert facts.fit("party", None) == ({}, [])
    assert facts.validation_errors(ValidationError.from_exception_data("x", [])) == []


def test_all_day_bounds_cover_days_with_23_and_25_hours() -> None:
    start, end = allday.bounds(date(2026, 3, 29), date(2026, 3, 29), "Europe/Berlin")
    assert (end - start).total_seconds() == 23 * 3600
    start, end = allday.bounds(date(2026, 10, 25), date(2026, 10, 25), "Europe/Berlin")
    assert (end - start).total_seconds() == 25 * 3600
    start, end = allday.bounds(date(2026, 10, 25), date(2026, 10, 27), "Europe/Berlin")
    assert start == datetime(2026, 10, 24, 22, tzinfo=UTC) and end == datetime(
        2026, 10, 27, 23, tzinfo=UTC
    )


def row(**over: object) -> Event:
    return event(
        **{"all_day": False, "starts_on": None, "ends_on": None, "tzid": "Europe/Berlin", **over}
    )


def test_resolve_leaves_unrelated_changes_alone() -> None:
    assert allday.resolve(row(), {"title": "x"}) == {"title": "x"}
    assert allday.resolve(row(), {"starts_at": NOW}) == {"starts_at": NOW}


def test_resolve_turns_days_into_instants_and_defaults_the_last_day() -> None:
    result = allday.resolve(row(), {"all_day": True, "starts_on": date(2026, 11, 3)})
    assert result["ends_on"] == date(2026, 11, 3) and result["end_estimated"] is False
    assert result["ends_at"] == datetime(2026, 11, 3, 23, tzinfo=UTC)
    long = allday.resolve(
        row(), {"all_day": True, "starts_on": date(2026, 11, 3), "ends_on": date(2026, 11, 4)}
    )
    assert long["ends_at"] == datetime(2026, 11, 4, 23, tzinfo=UTC)


def test_resolve_keeps_the_length_when_only_the_end_or_nothing_changes() -> None:
    current = row(all_day=True, starts_on=date(2026, 11, 3), ends_on=date(2026, 11, 5))
    assert allday.resolve(current, {"all_day": True})["ends_on"] == date(2026, 11, 5)
    assert allday.resolve(current, {"ends_on": date(2026, 11, 6)})["ends_on"] == date(2026, 11, 6)
    moved = allday.resolve(current, {"starts_on": date(2026, 11, 10)})
    assert moved["ends_on"] == date(2026, 11, 10)


@pytest.mark.parametrize(
    ("current", "changes", "code"),
    [
        ({}, {"all_day": True}, None),
        ({}, {"all_day": True, "starts_on": date(2026, 11, 3), "starts_at": NOW}, None),
        ({}, {"all_day": True, "starts_on": date(2026, 11, 3), "ends_on": date(2026, 11, 2)}, None),
        ({}, {"starts_on": date(2026, 11, 3)}, None),
        (
            {"all_day": True, "starts_on": date(2026, 11, 3), "ends_on": date(2026, 11, 3)},
            {"all_day": False},
            "times_required",
        ),
        (
            {"all_day": True, "starts_on": date(2026, 11, 3), "ends_on": date(2026, 11, 3)},
            {"starts_at": NOW},
            None,
        ),
    ],
)
def test_resolve_refuses_inconsistent_changes(
    current: dict, changes: dict, code: str | None
) -> None:
    with pytest.raises(ValidationProblem) as caught:
        allday.resolve(row(**current), changes)
    if code:
        assert caught.value.code == code


def test_resolve_switches_back_to_timed_with_both_instants() -> None:
    current = row(all_day=True, starts_on=date(2026, 11, 3), ends_on=date(2026, 11, 3))
    result = allday.resolve(current, {"all_day": False, "starts_at": NOW, "ends_at": NOW})
    assert result["starts_on"] is None and result["ends_on"] is None and result["all_day"] is False


def test_location_guard_cases() -> None:
    venue = uuid4()
    assert location_is_confirmed(row(venue_id=venue, venue_text="x", location_precision="hidden"))
    assert location_is_confirmed(row(venue_text=None)) and location_is_confirmed(
        row(venue_text="  ")
    )
    assert not location_is_confirmed(row(venue_text="Saal", location_precision="hidden"))
    assert not location_is_confirmed(
        row(venue_text="Saal", location_precision="building", location_confirmed_at=None)
    )
    assert location_is_confirmed(
        row(venue_text="Saal", location_precision="building", location_confirmed_at=NOW)
    )
    assert not location_is_confirmed(
        row(venue_text="Saal", location_precision="hidden", location_confirmed_at=NOW)
    )
    blocked = guards.location_confirmed(snap(location_confirmed=False), actor("editor"), NOW)
    assert [r.code for r in blocked] == ["location_unconfirmed"]
    assert guards.location_confirmed(snap(), actor("editor"), NOW) == []


def test_outcome_is_set_rules() -> None:
    assert not outcome_is_set(row()) and not outcome_is_set(row(outcome={}))
    assert not outcome_is_set(row(outcome={"attendance": 5}))
    assert not outcome_is_set(row(outcome={"costsCents": 0}))
    assert outcome_is_set(row(outcome={"attendance": 0, "costsCents": 0}))
    assert outcome_is_set(row(outcome={"waived": True, "waivedReason": "Gute Gründe hier."}))
    assert not outcome_is_set(row(outcome={"waived": True, "waivedReason": "kurz"}))
    assert not outcome_is_set(row(outcome={"waived": True}))


def test_snapshot_builders_set_m5_fields() -> None:
    current = row(
        venue_text="Saal",
        outcome={"attendance": 1, "costsCents": 2},
        all_day=True,
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 1, 1),
        format_id=uuid4(),
        facts={},
    )
    built = snapshot_of(current, None)
    assert built.location_confirmed is False and built.outcome_set is True
    assert (
        built.all_day
        and built.starts_on == date(2026, 1, 1)
        and built.format_id == current.format_id
    )
    full = snapshot_with(
        current,
        None,
        GuardData(
            open_required_followup=2,
            retrospective_filled=True,
            howto_present=True,
            required_profile="party",
        ),
        None,
    )
    assert full.open_required_followup == 2 and full.retrospective_filled is True
    assert full.howto_verified is False and full.facts_error == "facts.ageLimit"
    verified = snapshot_with(
        row(howto_verified_at=NOW, facts={"ageLimit": 18}),
        None,
        GuardData(howto_present=True, required_profile="party"),
        None,
    )
    assert verified.howto_verified is True and verified.facts_error is None
    nothing_to_verify = snapshot_with(row(), None, GuardData(), None)
    assert (
        nothing_to_verify.howto_verified is True and nothing_to_verify.retrospective_filled is False
    )
    assert isinstance(nothing_to_verify, Snapshot) and SimpleNamespace
