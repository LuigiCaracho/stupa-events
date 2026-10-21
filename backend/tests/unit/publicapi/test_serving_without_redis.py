"""Without Redis the calendar is built live and no rebuild is requested."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from app.modules.publicapi import cache, service, serving
from tests._support.factories import make_settings


async def test_the_live_calendar_without_redis_requests_no_rebuild(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def nothing(*_: Any, **__: Any) -> None:
        return None

    async def no_rows(*_: Any, **__: Any) -> list[Any]:
        return []

    monkeypatch.setattr(cache, "load", nothing)
    monkeypatch.setattr(service, "ics_rows", no_rows)
    document = await serving.ics_document(
        None,
        None,
        cache.ICS_ALL,
        None,
        make_settings(),
        now=datetime(2026, 10, 20, tzinfo=UTC),  # type: ignore[arg-type]
    )
    assert document is not None and document.body.startswith(b"BEGIN:VCALENDAR")
