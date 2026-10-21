"""`missing_info` is pure: every code alone, the weight of `no_poster`, and combinations."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.modules.events.hints import Hint, HintInput, PosterFacts, missing_info, warning_count

NOW = datetime(2026, 11, 20, 12, tzinfo=UTC)
GOOD_POSTER = PosterFacts("clean", True, "Alt", "Foto: Ada", False, None)
COMPLETE = HintInput(
    state="published",
    now=NOW,
    ends_at=NOW + timedelta(days=3),
    summary="Ein Film.",
    primary_category_id=uuid4(),
    venue_id=uuid4(),
    venue_text=None,
    location_confirmed=True,
    poster=GOOD_POSTER,
    facts_error=None,
    howto_present=True,
    outcome_answered=False,
)


def codes(item: HintInput) -> list[str]:
    return [hint.code for hint in missing_info(item)]


def test_a_complete_dossier_has_no_hint() -> None:
    assert missing_info(COMPLETE) == []


@pytest.mark.parametrize(
    ("change", "code", "severity"),
    [
        ({"poster": None}, "no_poster", "warn"),
        ({"poster": None, "state": "draft"}, "no_poster", "info"),
        ({"poster": replace(GOOD_POSTER, alt_text=" ")}, "poster_alt_missing", "info"),
        ({"poster": replace(GOOD_POSTER, credit=None)}, "poster_credit_missing", "info"),
        (
            {"poster": replace(GOOD_POSTER, persons_depicted=True)},
            "poster_consent_missing",
            "warn",
        ),
        ({"poster": replace(GOOD_POSTER, scan_status="pending")}, "poster_not_ready", "warn"),
        ({"poster": replace(GOOD_POSTER, scan_status="infected")}, "poster_not_ready", "warn"),
        ({"poster": replace(GOOD_POSTER, has_derivatives=False)}, "poster_not_ready", "warn"),
        ({"summary": "  "}, "no_summary", "info"),
        ({"primary_category_id": None}, "no_category", "info"),
        ({"venue_id": None, "venue_text": " "}, "no_venue", "info"),
        (
            {"venue_id": None, "venue_text": "Saal", "location_confirmed": False},
            "location_unconfirmed",
            "warn",
        ),
        ({"facts_error": "facts.ageLimit"}, "facts_incomplete", "info"),
        ({"howto_present": False}, "howto_missing", "info"),
        ({"ends_at": NOW - timedelta(hours=1)}, "outcome_open", "info"),
    ],
)
def test_each_code_alone(change: dict, code: str, severity: str) -> None:
    hints = missing_info(replace(COMPLETE, **change))
    assert [(h.code, h.severity) for h in hints] == [(code, severity)]


def test_the_field_points_at_the_place_to_fix() -> None:
    hints = missing_info(replace(COMPLETE, poster=None, facts_error="facts.ageLimit"))
    assert hints == [
        Hint("no_poster", "warn", "poster"),
        Hint("facts_incomplete", "info", "facts.ageLimit"),
    ]


def test_an_answered_outcome_closes_the_hint() -> None:
    over = replace(COMPLETE, ends_at=NOW - timedelta(hours=1), outcome_answered=True)
    assert missing_info(over) == []


def test_a_free_venue_text_that_is_confirmed_raises_no_hint() -> None:
    item = replace(COMPLETE, venue_id=None, venue_text="Saal", location_confirmed=True)
    assert missing_info(item) == []


def test_combined_hints_keep_the_order_and_count_the_warnings() -> None:
    item = replace(
        COMPLETE,
        poster=None,
        summary=None,
        primary_category_id=None,
        howto_present=False,
        ends_at=NOW - timedelta(days=1),
    )
    assert codes(item) == [
        "no_poster",
        "no_summary",
        "no_category",
        "howto_missing",
        "outcome_open",
    ]
    assert warning_count(missing_info(item)) == 1
    assert warning_count([]) == 0
