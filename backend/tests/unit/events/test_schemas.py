"""Request rules of the contract (4.2): lengths, awareness, order, control characters, allDay."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.events.schemas import EventCreate, EventPatch, ImageExceptionIn, TransitionIn

BASE: dict[str, Any] = {
    "title": "Movienight",
    "startsAt": "2026-11-05T18:00:00+01:00",
    "endsAt": "2026-11-05T21:00:00+01:00",
    "organizationId": str(uuid4()),
}


def build(**over: Any) -> EventCreate:
    return EventCreate.model_validate({**BASE, **over})


def test_defaults_and_trimming() -> None:
    event = build(title="  Kino  ", venueText="  ")
    assert event.title == "Kino" and event.venue_text is None and event.tzid == "Europe/Berlin"
    assert event.all_day is False


@pytest.mark.parametrize(
    "over",
    [
        {"title": ""},
        {"title": "x" * 201},
        {"title": "a\nb"},
        {"summary": "x" * 201},
        {"summary": "a b"},
        {"venueText": "a\x07b"},
        {"startsAt": "2026-11-05T18:00:00"},
        {"endsAt": "2026-11-05T17:00:00+01:00"},
        {"tzid": "UTC"},
        {"allDay": True},
        {"unknown": 1},
    ],
)
def test_create_rejects(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        build(**over)


def test_equal_start_and_end_is_allowed() -> None:
    assert build(endsAt=BASE["startsAt"]).ends_at == build().starts_at


def test_patch_needs_a_revision_and_tracks_given_fields() -> None:
    with pytest.raises(ValidationError):
        EventPatch.model_validate({"title": "x"})
    patch = EventPatch.model_validate({"rev": 2, "venueText": None})
    assert patch.model_fields_set == {"rev", "venue_text"}
    with pytest.raises(ValidationError):
        EventPatch.model_validate({"rev": 0})
    with pytest.raises(ValidationError):
        EventPatch.model_validate({"rev": 1, "allDay": True})


def test_note_and_exception_reason_limits() -> None:
    assert TransitionIn.model_validate({}).note is None
    with pytest.raises(ValidationError):
        TransitionIn.model_validate({"note": "x" * 501})
    assert (
        ImageExceptionIn.model_validate({"reason": "  zehn Zeichen!  "}).reason == "zehn Zeichen!"
    )
    for reason in ("kurz", "   neun   z", "x" * 501):
        with pytest.raises(ValidationError):
            ImageExceptionIn.model_validate({"reason": reason})
