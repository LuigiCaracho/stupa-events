"""The M1 acceptance path through the real API and database."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def test_organizer_to_live_with_poster(api: Api) -> None:
    event = await api.create_event()
    assert event["state"] == "idea" and event["rev"] == 1 and event["createdBy"] == "sub-org-fsi"
    eid = event["id"]
    assert (await api.fire("organizer-fsi", eid, "T01")).json()["state"] == "planning"
    poster = await api.upload_poster("organizer-fsi", eid)
    assert poster.status_code == 201 and poster.json()["scanStatus"] == "pending"
    assert api.queue.enqueued
    assert await api.process_poster(poster.json()["id"]) == "clean"
    submitted = (await api.fire("organizer-fsi", eid, "T02")).json()
    assert submitted["state"] == "in_review" and submitted["submittedBy"] == "sub-org-fsi"
    approved = (await api.fire("editor", eid, "T04")).json()
    assert approved["state"] == "approved" and approved["approvedBy"] == "sub-editor"
    assert approved["slug"].endswith("-movienight-film-a")
    live = (await api.fire("editor", eid, "T05")).json()
    assert live["state"] == "live"
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()
    assert [item["id"] for item in feed["items"]] == [eid]
    assert feed["items"][0]["image"]["url"].endswith("-card_1200.webp")


async def test_without_poster_t04_is_422_image_required(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    await api.fire("organizer-fsi", eid, "T02")
    response = await api.fire("editor", eid, "T04")
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "image_required"
    assert body["reasons"][0] == {
        "code": "image_required",
        "field": "poster",
        "severity": "blocker",
        "messageKey": "guards.image_required",
        "fixAction": "upload_poster",
    }
    assert body["type"] == "app://error/image_required"


async def test_image_exception_allows_publication_and_feed_has_no_image(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    await api.fire("organizer-fsi", eid, "T02")
    short = await api.request(
        "editor", "POST", f"/api/events/{eid}/image-exception", json={"reason": "kurz"}
    )
    assert short.status_code == 422
    granted = await api.request(
        "editor",
        "POST",
        f"/api/events/{eid}/image-exception",
        json={"reason": "Hochschulveranstaltung ohne Motiv"},
    )
    assert (
        granted.status_code == 200 and granted.json()["imageException"]["grantedBy"] == "sub-editor"
    )
    assert (await api.fire("editor", eid, "T04")).status_code == 200
    assert (await api.fire("editor", eid, "T05")).status_code == 200
    item = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"][0]
    assert item["image"] is None
    event_now = (await api.request("editor", "GET", f"/api/events/{eid}")).json()
    assert "imageException" in event_now and "reason" in event_now["imageException"]


async def test_exception_is_editor_only_and_one_event_only(api: Api) -> None:
    first = await api.create_event()
    second = await api.create_event(title="Zweites Event")
    denied = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{first['id']}/image-exception",
        json={"reason": "ohne Motiv, bitte"},
    )
    assert denied.status_code == 403
    await api.request(
        "editor",
        "POST",
        f"/api/events/{first['id']}/image-exception",
        json={"reason": "ohne Motiv, bitte"},
    )
    other = (await api.request("editor", "GET", f"/api/events/{second['id']}")).json()
    assert other["imageException"] is None
