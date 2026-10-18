"""A board card names the same blockers as `GET /guards/{T}`, also those that need a query."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def card_of(api: Api, user: str, eid: str) -> dict:
    board = (await api.request(user, "GET", "/api/events?view=board")).json()
    return next(c for col in board["columns"] for c in col["items"] if c["id"] == eid)


async def guard_codes(api: Api, user: str, eid: str, tid: str) -> list[str]:
    response = await api.request(user, "GET", f"/api/events/{eid}/guards/{tid}")
    return [r["code"] for r in response.json()["reasons"] if r["severity"] == "blocker"]


async def test_a_quarantined_attachment_blocks_on_the_card_too(api: Api) -> None:
    event = await api.approved_ready_event()
    eid = event["id"]
    await api.sql(
        "INSERT INTO attachment (event_id, display_name, storage_name, mime, size_bytes, sha256, "
        "scan_status) VALUES (:e, 'x.pdf', 'x', 'application/pdf', 1, 'bb', 'pending')",
        e=eid,
    )
    card = await card_of(api, "editor", eid)
    assert await guard_codes(api, "editor", eid, "T04") == ["attachment_quarantined"]
    assert card["nextTransition"] == "T04"
    assert [b["code"] for b in card["blockers"]] == ["attachment_quarantined"]


async def test_a_poster_reused_from_another_year_blocks_on_the_card_too(api: Api) -> None:
    first = await api.to_state("planning")
    poster = await api.upload_poster("organizer-fsi", first["id"])
    await api.process_poster(poster.json()["id"])
    other = await api.to_state(
        "planning",
        title="Anderes Jahr",
        startsAt=future(400).isoformat(),
        endsAt=future(400, 2).isoformat(),
    )
    same_file = await api.upload_poster("organizer-fsi", other["id"])
    await api.process_poster(same_file.json()["id"])
    await api.fire("organizer-fsi", other["id"], "T02")
    card = await card_of(api, "editor", other["id"])
    assert "flyer_date" in await guard_codes(api, "editor", other["id"], "T04")
    assert "flyer_date" in [b["code"] for b in card["blockers"]]
    fresh = await card_of(api, "editor", first["id"])
    assert "flyer_date" not in [b["code"] for b in fresh["blockers"]]
