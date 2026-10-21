"""Hint inputs from poster rows and revision payloads from event rows."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.modules.events.hints_data import outcome_answered, poster_facts
from app.modules.events.models import Event
from app.modules.events.revisions import revision_payload

NOW = datetime(2026, 11, 20, 12, tzinfo=UTC)


def event(**over: object) -> Event:
    base = {
        "id": uuid4(),
        "state": "draft",
        "title": "T",
        "summary": "S",
        "starts_at": datetime(2026, 11, 1, tzinfo=UTC),
        "ends_at": datetime(2026, 11, 2, tzinfo=UTC),
        "organization_id": uuid4(),
        "primary_category_id": None,
        "venue_text": "Raum",
        "created_by": "me",
        "hero_attachment_id": None,
        "public_status": "scheduled",
        "rev": 3,
    }
    return Event(**{**base, **over})


def poster(**over: object) -> SimpleNamespace:
    base = {
        "retired_at": None,
        "scan_status": "clean",
        "derivatives": {"thumb_400": {}},
        "alt_text": "a",
        "credit": "c",
        "persons_depicted": False,
        "consent_note": None,
    }
    return SimpleNamespace(**{**base, **over})


def test_poster_facts_ignore_retired_and_missing() -> None:
    assert poster_facts(None) is None
    assert poster_facts(poster(retired_at=datetime.now(UTC))) is None  # type: ignore[arg-type]
    assert poster_facts(poster()).ready is True  # type: ignore[arg-type, union-attr]
    assert poster_facts(poster(derivatives=None)).ready is False  # type: ignore[arg-type, union-attr]
    assert poster_facts(poster(scan_status="pending")).ready is False  # type: ignore[arg-type, union-attr]


def test_poster_consent_follows_the_depicted_persons() -> None:
    open_consent = poster_facts(poster(persons_depicted=True))  # type: ignore[arg-type]
    assert open_consent is not None and open_consent.consent_missing is True
    given = poster_facts(poster(persons_depicted=True, consent_note="Einverständnis liegt vor"))  # type: ignore[arg-type]
    assert given is not None and given.consent_missing is False


def test_outcome_answered_by_a_figure_a_note_or_the_waiver() -> None:
    assert not outcome_answered(None) and not outcome_answered({})
    assert not outcome_answered({"waived": False, "attendance": None})
    assert outcome_answered({"attendance": 0}) and outcome_answered({"notes": "Lief gut"})
    assert outcome_answered({"costsCents": 5}) and outcome_answered({"waived": True})


def test_revision_payload_is_json_ready() -> None:
    payload = revision_payload(event())
    assert payload["starts_at"] == "2026-11-01T00:00:00+00:00"
    assert isinstance(payload["id"], str) and payload["rev"] == 3
    assert "image_exception" not in payload and "submitted_by" not in payload
