"""The outcome model and the missing-parts helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.modules.followup.missing import days_open, missing_of
from app.modules.followup.schemas import OutcomeIn
from app.shared.errors import ValidationProblem
from tests.unit.pipeline.support import snap


def test_limits_and_defaults() -> None:
    empty = OutcomeIn.model_validate({})
    assert empty.attendance is None and empty.waived is False
    assert OutcomeIn.model_validate({"attendance": 0, "costsCents": 0}).stored()["costsCents"] == 0
    for bad in (
        {"attendance": -1},
        {"costsCents": -5},
        {"notes": "x" * 2001},
        {"waivedReason": "x" * 301},
        {"unknown": 1},
        {"notes": "Tab\tinside"},
        {"waivedReason": "zwei\nZeilen"},
    ):
        with pytest.raises(ValidationError):
            OutcomeIn.model_validate(bad)


def test_notes_keep_newlines_and_are_trimmed() -> None:
    body = OutcomeIn.model_validate({"notes": "  eins\nzwei  ", "waivedReason": "  "})
    assert body.notes == "eins\nzwei" and body.waived_reason is None


def test_a_waiver_clears_the_numbers_and_needs_ten_characters() -> None:
    body = OutcomeIn.model_validate(
        {
            "attendance": 5,
            "costsCents": 5,
            "revenueCents": 5,
            "waived": True,
            "waivedReason": "Zehn Zeichen.",
        }
    )
    assert body.attendance is None and body.costs_cents is None and body.revenue_cents is None
    assert body.stored()["waived"] is True and body.stored()["waivedReason"] == "Zehn Zeichen."
    for reason in (None, "", "neun Zei"):
        with pytest.raises(ValidationProblem) as caught:
            OutcomeIn.model_validate({"waived": True, "waivedReason": reason}).stored()
        assert caught.value.code == "waiver_reason_required"


def test_missing_parts_in_guard_order() -> None:
    assert missing_of(snap()) == []
    open_all = snap(
        open_required_followup=1,
        retrospective_filled=False,
        outcome_set=False,
        howto_verified=False,
    )
    assert missing_of(open_all) == ["checklist", "retrospective", "outcome", "howto"]
    assert missing_of(snap(outcome_set=False)) == ["outcome"]


def test_days_open() -> None:
    now = datetime(2026, 11, 20, tzinfo=UTC)
    assert days_open(now - timedelta(days=8, hours=3), now) == 8
    assert days_open(None, now) == 0 and days_open(now + timedelta(days=1), now) == 0
