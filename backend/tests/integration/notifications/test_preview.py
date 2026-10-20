"""`render_preview` builds the catalog context from a real dossier (local time, empty venue)."""

from __future__ import annotations

import pytest

from app.modules.notifications.preview import render_preview
from app.shared.errors import ValidationProblem
from tests.integration.events.harness import Api
from tests.integration.notifications.conftest import load_event

pytestmark = pytest.mark.integration


async def test_render_preview_local_time_and_names(api: Api) -> None:
    event = await api.create_event(venueText=None)
    await api.sql(
        "UPDATE event SET starts_at = '2026-07-04 16:00+00', ends_at = '2026-07-04 18:00+00' "
        "WHERE id = :i",
        i=event["id"],
    )
    async with api.maker() as session:
        row = await load_event(session, event["id"])
        subject, body = await render_preview(
            session,
            row,
            "{{ event.title }}",
            "{{ event.starts_local }}|{{ venue.name }}|{{ org.name }}",
        )
        assert subject == row.title
        assert body.startswith("04.07.2026, 18:00 Uhr|")
        assert body.split("|")[1] == ""
        with pytest.raises(ValidationProblem) as err:
            await render_preview(session, row, "x", "{{ event.raum }}")
        assert (err.value.extensions or {})["reasons"][0]["field"] == "event.raum"
