"""Request rules of the contract (4.2): lengths, awareness, order, control characters, allDay."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.events.schemas import CancelIn, EventCreate, EventPatch, PostponeIn

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
        {"organizationId": None},
    ],
)
def test_create_rejects(over: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        build(**over)


def test_equal_start_and_end_is_allowed() -> None:
    assert build(endsAt=BASE["startsAt"]).ends_at == build().starts_at


def test_patch_tracks_given_fields_and_takes_an_optional_revision() -> None:
    assert EventPatch.model_validate({"title": "x"}).rev is None
    patch = EventPatch.model_validate({"rev": 2, "venueText": None})
    assert patch.model_fields_set == {"rev", "venue_text"}
    with pytest.raises(ValidationError):
        EventPatch.model_validate({"rev": 0})
    assert EventPatch.model_validate({"rev": 1, "allDay": True}).all_day is True


def test_the_organization_is_required_to_create() -> None:
    body = {k: v for k, v in BASE.items() if k != "organizationId"}
    with pytest.raises(ValidationError):
        EventCreate.model_validate(body)


def test_patch_takes_the_organization_for_the_editorial_team() -> None:
    org = uuid4()
    assert EventPatch.model_validate({"organizationId": str(org)}).organization_id == org


def test_reason_and_public_text_limits() -> None:
    assert CancelIn.model_validate({}).reason is None
    assert (
        PostponeIn.model_validate({"newStartsAt": "2026-12-01T10:00:00+01:00"}).new_ends_at is None
    )
    for bad in ({"reason": "x" * 501}, {"publicReasonText": "x" * 141}, {"publicReasonCode": "x"}):
        with pytest.raises(ValidationError):
            CancelIn.model_validate(bad)
