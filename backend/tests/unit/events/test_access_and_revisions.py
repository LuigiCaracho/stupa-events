"""Snapshot building and revision payloads from event rows."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

from app.modules.events.access import (
    poster_snapshot,
    snapshot_of,
    valid_exception_reason,
)
from app.modules.events.models import Event
from app.modules.events.revisions import revision_payload


def event(**over: object) -> Event:
    base = {
        "id": uuid4(),
        "state": "planning",
        "title": "T",
        "summary": "S",
        "starts_at": datetime(2026, 11, 1, tzinfo=UTC),
        "ends_at": datetime(2026, 11, 2, tzinfo=UTC),
        "organization_id": uuid4(),
        "primary_category_id": None,
        "venue_text": "Raum",
        "created_by": "me",
        "submitted_by": None,
        "image_exception": None,
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
        "rights_basis": "own_work",
        "persons_depicted": False,
        "consent_note": None,
        "created_at": None,
    }
    return SimpleNamespace(**{**base, **over})


def test_exception_reason_needs_ten_characters() -> None:
    assert valid_exception_reason(event()) is None
    assert valid_exception_reason(event(image_exception={"reason": "short"})) is None
    assert valid_exception_reason(
        event(image_exception={"reason": " Hochschulveranstaltung "})
    ) == ("Hochschulveranstaltung")
    assert valid_exception_reason(event(image_exception={})) is None


def test_poster_snapshot_ignores_retired_and_missing() -> None:
    assert poster_snapshot(None) is None
    assert poster_snapshot(poster(retired_at=datetime.now(UTC))) is None  # type: ignore[arg-type]
    assert poster_snapshot(poster()).usable is True  # type: ignore[arg-type, union-attr]
    assert poster_snapshot(poster(derivatives=None)).usable is False  # type: ignore[arg-type, union-attr]


def test_snapshot_of_carries_the_guard_inputs() -> None:
    snapshot = snapshot_of(event(image_exception={"reason": "Hochschulveranstaltung"}), poster())  # type: ignore[arg-type]
    assert (
        snapshot.state == "planning" and snapshot.image_exception_reason == "Hochschulveranstaltung"
    )
    assert snapshot.poster is not None and snapshot.created_by == "me"


def test_revision_payload_is_json_ready() -> None:
    payload = revision_payload(event())
    assert payload["starts_at"] == "2026-11-01T00:00:00+00:00"
    assert isinstance(payload["id"], str) and payload["rev"] == 3
