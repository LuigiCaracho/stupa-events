"""The outcome model."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.followup.schemas import OutcomeIn


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


def test_a_waiver_clears_the_numbers_and_needs_no_reason() -> None:
    body = OutcomeIn.model_validate(
        {"attendance": 5, "costsCents": 5, "revenueCents": 5, "waived": True}
    )
    assert body.attendance is None and body.costs_cents is None and body.revenue_cents is None
    assert body.stored()["waived"] is True and body.stored()["waivedReason"] is None
    given = OutcomeIn.model_validate({"waived": True, "waivedReason": "Kein Interesse."})
    assert given.stored()["waivedReason"] == "Kein Interesse."
