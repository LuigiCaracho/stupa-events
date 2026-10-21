"""Review findings kept alive: mandatory If-Match, stale versions, internal notes, revert derivations."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


@pytest.mark.parametrize(
    ("name", "state", "body"),
    [
        ("publish", "draft", {}),
        ("unpublish", "published", {}),
        ("archive", "published", {}),
        ("restore", "archived", {}),
        ("cancel", "published", {"reason": "x", "publicReasonCode": "other"}),
        ("postpone", "published", {"reason": "x", "publicReasonCode": "other"}),
        ("reinstate", "published", {"reason": "x"}),
        ("revert-revision", "published", {"rev": 1}),
    ],
)
async def test_every_action_needs_an_if_match(api: Api, name: str, state: str, body: dict) -> None:
    event = await api.to_state(state)
    response = await api.act("editor", event["id"], name, without_if_match=True, **body)
    assert response.status_code == 428
    path = (
        name
        if name in {"publish", "unpublish", "archive", "restore", "cancel", "postpone", "reinstate"}
        else f"actions/{name}"
    )
    star = await api.request(
        "editor",
        "POST",
        f"/api/events/{event['id']}/{path}",
        json=body,
        headers={"If-Match": "*"},
    )
    assert star.status_code == 428


async def test_publishing_a_stale_version_conflicts(api: Api) -> None:
    event = await api.create_event()
    stale = event["rev"]
    await api.patch("editor", event["id"], summary="Korrigiert")
    response = await api.act("editor", event["id"], "publish", if_match_rev=stale)
    assert response.status_code == 409 and response.json()["code"] == "conflict"


async def test_change_notes_stay_internal(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    await api.patch("organizer-fsi", eid, summary="Neu gefasst")
    reverted = await api.act("organizer-fsi", eid, "revert-revision", rev=event["rev"])
    assert reverted.status_code == 200, reverted.text
    inside = (await api.request("editor", "GET", f"/api/events/{eid}/revisions")).json()
    assert any(r["changeNote"] for r in inside["items"])
    detail = (await api.request("editor", "GET", f"/api/events/{eid}/revisions/1")).json()
    assert "createdBy" in detail["snapshot"]
    outside = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/revisions")).json()
    assert all(r["changeNote"] is None for r in outside["items"])
    masked = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/revisions/1")).json()
    assert "createdBy" not in masked["snapshot"]


async def test_a_chunked_draft_body_is_capped_before_it_is_read(api: Api) -> None:
    event = await api.create_event()

    async def chunks():  # noqa: ANN202
        for _ in range(100):
            yield b"x" * 1024

    response = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{event['id']}/draft",
        content=chunks(),
        headers={"If-Match": f'"{event["rev"]}"', "content-type": "application/json"},
    )
    assert response.status_code == 413


async def test_a_revert_of_the_venue_text_hides_it_again_until_it_is_confirmed(api: Api) -> None:
    event = await api.to_state("published", venueText="Saal im Rathaus")
    eid, first = event["id"], event["rev"]
    changed = await api.patch("editor", eid, venueText="Privatweg 5, Reutlingen")
    assert changed.status_code == 200, changed.text
    await api.confirm_location(eid)
    shown = await api.request(None, "GET", "/api/public/feed/events")
    assert "Privatweg 5" in shown.text
    reverted = await api.act("editor", eid, "revert-revision", rev=first)
    assert reverted.status_code == 200, reverted.text
    after = await api.get("editor", eid)
    assert after["venueText"] == "Saal im Rathaus" and after["locationPrecision"] == "hidden"
    feed = await api.request(None, "GET", "/api/public/feed/events")
    assert "Privatweg" not in feed.text and "Saal im Rathaus" not in feed.text


async def test_a_revert_of_an_all_day_event_moves_its_days_with_the_instants(api: Api) -> None:
    event = await api.to_state(
        "published", allDay=True, startsOn=future(10).date().isoformat(), startsAt=None, endsAt=None
    )
    eid, first = event["id"], event["rev"]
    moved = await api.patch("editor", eid, startsOn=future(20).date().isoformat())
    assert moved.status_code == 200, moved.text
    reverted = await api.act("editor", eid, "revert-revision", rev=first)
    assert reverted.status_code == 200, reverted.text
    after = await api.get("editor", eid)
    assert after["startsOn"] == event["startsOn"] and after["endsOn"] == event["endsOn"]


async def test_a_revert_across_the_all_day_switch_is_refused(api: Api) -> None:
    event = await api.to_state("published")
    first = event["rev"]
    await api.sql(
        "UPDATE event SET all_day = true, starts_on = current_date, ends_on = current_date"
    )
    refused = await api.act("editor", event["id"], "revert-revision", rev=first)
    assert refused.status_code == 409 and refused.json()["code"] == "revert_allday_changed"
