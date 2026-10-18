"""The feed and the media route against the real view and the `events_public` role."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema_rs
import pytest
from sqlalchemy import text

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration

SCHEMA = jsonschema_rs.validator_for(
    json.loads((Path(__file__).resolve().parents[2] / "schema" / "feed-v2.json").read_text())
)
FEED = "/api/public/feed/events"


async def go_live(api: Api, **over: object) -> dict:
    ready = await api.approved_ready_event() if not over else await ready_with(api, **over)
    await api.fire("editor", ready["id"], "T04")
    return (await api.fire("editor", ready["id"], "T05")).json()


async def ready_with(api: Api, user: str = "organizer-fsi", **over: object) -> dict:
    event = await api.create_event(user=user, **over)
    eid = event["id"]
    await api.fire(user, eid, "T01")
    poster = await api.upload_poster(user, eid)
    await api.process_poster(poster.json()["id"])
    await api.fire(user, eid, "T02")
    return (await api.request("editor", "GET", f"/api/events/{eid}")).json()


async def test_public_feed_schema(api: Api) -> None:
    live = await go_live(api)
    response = await api.request(None, "GET", FEED)
    assert response.status_code == 200
    SCHEMA.validate(response.json())
    item = response.json()["items"][0]
    assert item["id"] == live["id"] and item["slug"] == live["slug"]
    assert item["organization"]["short"] == "FSI" and item["venueText"] == "Kinosaal 9-133"
    assert item["categories"][0]["slug"] == "kino" and item["status"] == "scheduled"
    assert item["image"]["alt"] == "Ein Filmplakat" and item["image"]["credit"] == "Foto: Ada"
    assert item["image"]["width"] == 1200 and item["url"].endswith(f"/e/{live['slug']}")
    assert response.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=60"
    assert "access-control-allow-origin" not in response.headers


async def test_only_published_events_with_image_or_exception_are_listed(api: Api) -> None:
    drafts = [await api.create_event(title=f"Entwurf {n}") for n in range(2)]
    await api.fire("organizer-fsi", drafts[1]["id"], "T01")
    in_review = await ready_with(api, title="Zur Freigabe")
    approved = await ready_with(api, title="Freigegeben")
    await api.fire("editor", approved["id"], "T04")
    assert in_review["state"] == "in_review"
    assert (await api.request(None, "GET", FEED)).json()["items"] == []
    live = await go_live(api, title="Veröffentlicht")
    items = (await api.request(None, "GET", FEED)).json()["items"]
    assert [i["id"] for i in items] == [live["id"]]


async def test_dossier_data_never_reaches_the_feed(api: Api) -> None:
    await api.create_event()
    await go_live(api, title="Mit Notiz")
    raw = (await api.request(None, "GET", FEED)).text
    for secret in (
        "sub-org-fsi",
        "sub-editor",
        "createdBy",
        "approvedBy",
        "imageException",
        "rev",
        "hero",
    ):
        assert secret not in raw, secret


async def test_exception_event_is_listed_without_image(api: Api) -> None:
    event = await api.create_event(title="Ohne Bild")
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    await api.fire("organizer-fsi", eid, "T02")
    await api.request(
        "editor",
        "POST",
        f"/api/events/{eid}/image-exception",
        json={"reason": "Hochschulveranstaltung"},
    )
    await api.fire("editor", eid, "T04")
    await api.fire("editor", eid, "T05")
    item = (await api.request(None, "GET", FEED)).json()["items"][0]
    SCHEMA.validate((await api.request(None, "GET", FEED)).json())
    assert item["image"] is None


async def test_filters_order_limit(api: Api) -> None:
    later = await ready_with(
        api, title="B später", startsAt=future(20).isoformat(), endsAt=future(20, 2).isoformat()
    )
    sooner = await ready_with(
        api, title="A früher", startsAt=future(3).isoformat(), endsAt=future(3, 2).isoformat()
    )
    makers = await ready_with(api, user="organizer-makers", org="makers", title="Makers")
    for event in (later, sooner, makers):
        await api.fire("editor", event["id"], "T04")
        await api.fire("editor", event["id"], "T05")
    items = (await api.request(None, "GET", FEED)).json()["items"]
    assert [i["title"] for i in items] == ["A früher", "Makers", "B später"]
    assert len((await api.request(None, "GET", f"{FEED}?limit=1")).json()["items"]) == 1
    window = (
        await api.request(None, "GET", f"{FEED}?from={future(10).isoformat().replace('+', '%2B')}")
    ).json()
    assert [i["title"] for i in window["items"]] == ["Makers", "B später"]
    until = (
        await api.request(None, "GET", f"{FEED}?to={future(10).isoformat().replace('+', '%2B')}")
    ).json()
    assert [i["title"] for i in until["items"]] == ["A früher"]
    by_category = (await api.request(None, "GET", f"{FEED}?category=kino")).json()["items"]
    assert len(by_category) == 3
    assert (await api.request(None, "GET", f"{FEED}?category=party")).json()["items"] == []
    assert len((await api.request(None, "GET", f"{FEED}?org=fsi")).json()["items"]) == 2
    only_makers = (await api.request(None, "GET", f"{FEED}?org=makers")).json()["items"]
    assert [i["title"] for i in only_makers] == ["Makers"]


async def test_etag_and_304(api: Api) -> None:
    await go_live(api)
    first = await api.request(None, "GET", FEED)
    etag = first.headers["etag"]
    cached = await api.request(None, "GET", FEED, headers={"If-None-Match": etag})
    assert cached.status_code == 304 and cached.content == b""
    changed = await api.request(
        None, "GET", f"{FEED}?limit=1", headers={"If-None-Match": '"other"'}
    )
    assert changed.status_code == 200
    async with api.maker() as session:
        await session.execute(text("UPDATE event SET title = 'Geändert' WHERE state = 'live'"))
        await session.commit()
    after = await api.request(None, "GET", FEED, headers={"If-None-Match": etag})
    assert after.status_code == 200 and after.headers["etag"] != etag


async def test_followup_and_archived_stay_public_via_the_view(api: Api) -> None:
    live = await go_live(api)
    async with api.maker() as session:
        await session.execute(text("UPDATE event SET state = 'followup'"))
        await session.commit()
    assert len((await api.request(None, "GET", FEED)).json()["items"]) == 1
    async with api.maker() as session:
        await session.execute(text("UPDATE event SET state = 'withdrawn'"))
        await session.commit()
    assert (await api.request(None, "GET", FEED)).json()["items"] == []
    assert live


async def test_media_route(api: Api) -> None:
    live = await go_live(api)
    derivative = live["poster"]["derivatives"]["card1200"]["id"]
    response = await api.request(None, "GET", f"/api/public/media/{derivative}.webp")
    assert response.status_code == 200 and response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.content == api.public.blobs[f"derivatives/{derivative}.webp"]
    sha = derivative.split("-")[0]
    assert (
        await api.request(None, "GET", f"/api/public/media/{sha}-thumb_400.webp")
    ).status_code == 200
    assert (
        await api.request(None, "GET", f"/api/public/media/{'0' * 16}-card_1200.webp")
    ).status_code == 404


async def test_media_of_an_event_that_is_not_public_is_404(api: Api) -> None:
    ready = await ready_with(api)
    derivative = ready["poster"]["derivatives"]["card1200"]["id"]
    path = f"/api/public/media/{derivative}.webp"
    assert (await api.request(None, "GET", path)).status_code == 404
    await api.fire("editor", ready["id"], "T04")
    assert (await api.request(None, "GET", path)).status_code == 404


async def test_a_replaced_poster_gets_a_new_media_id(api: Api) -> None:
    from tests._support.factories import png_bytes

    event = await api.create_event()
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    ids = []
    for color in ("#aa0000", "#00aa00"):
        poster = (await api.upload_poster("organizer-fsi", eid, data=png_bytes(color=color))).json()
        await api.process_poster(poster["id"])
        ids.append(poster["sha256"][:16])
    assert ids[0] != ids[1]
