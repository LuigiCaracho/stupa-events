"""Builders for pure pipeline tests: snapshots, actors and a fixed clock."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.modules.pipeline.snapshot import Actor, PosterSnapshot, Snapshot
from app.shared.permissions import ROLE_PERMISSIONS

NOW = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
ORG = uuid4()
CATEGORY = uuid4()
GOOD_POSTER = PosterSnapshot("clean", True, "Alt", "Foto: Ada", "own_work")


def snap(**over: object) -> Snapshot:
    """A complete planning snapshot with a usable poster; `over` replaces fields."""
    base: dict[str, object] = {
        "state": "planning",
        "title": "Movienight",
        "summary": "Kurz und gut.",
        "starts_at": NOW + timedelta(days=3),
        "ends_at": NOW + timedelta(days=3, hours=3),
        "organization_id": ORG,
        "primary_category_id": CATEGORY,
        "venue_text": "Kinosaal",
        "created_by": "creator",
        "submitted_by": None,
        "poster": GOOD_POSTER,
        "image_exception_reason": None,
    }
    return Snapshot(**{**base, **over})  # type: ignore[arg-type]


def actor(role: str, sub: str = "someone") -> Actor:
    """An actor with the permissions of `role` in the organization of the snapshot."""
    return Actor(sub=sub, permissions=frozenset(ROLE_PERMISSIONS[role]))
