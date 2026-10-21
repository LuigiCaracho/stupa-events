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


async def draft_with_poster(api: Api, user: str = "organizer-fsi", **over: object) -> dict:
    event = await api.create_event(user=user, **over)
    await api.with_poster(event["id"], user)
    return await api.get("editor", event["id"])


async def go_live(api: Api, user: str = "organizer-fsi", **over: object) -> dict:
    event = await draft_with_poster(api, user, **over)
    await api.confirm_location(event["id"])
    published = await api.act(user, event["id"], "publish")
    assert published.status_code == 200, published.text
    return await api.get("editor", event["id"])


async def test_public_feed_schema(api: Api) -> None:
    live = await go_live(api)
    response = await api.request(None, "GET", FEED)
    assert response.status_code == 200
    SCHEMA.validate(response.json())
    item = response.json()["items"][0]
    assert item["id"] == live["id"] and item["slug"] == live["slug"]
    assert item["organization"]["short"] == "FSI" and item["organization"]["slug"] == "fsi"
    assert item["venueText"] == "Kinosaal 9-133"
    assert item["categories"][0]["slug"] == "kino" and item["status"] == "scheduled"
    assert item["image"]["alt"] == "Ein Filmplakat" and item["image"]["credit"] == "Foto: Ada"
    assert item["image"]["width"] == 1200 and item["url"].endswith(f"/e/{live['slug']}")
    assert response.headers["cache-control"] == "public, max-age=300, stale-while-revalidate=60"
    assert "access-control-allow-origin" not in response.headers


async def test_only_published_and_archived_events_are_listed(api: Api) -> None:
    await api.create_event(title="Entwurf")
    await draft_with_poster(api, title="Entwurf mit Bild")
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
        "submittedBy",
        "rev",
        "hero",
    ):
        assert secret not in raw, secret


async def test_an_event_without_image_is_listed_with_image_null(api: Api) -> None:
    event = await api.create_event(title="Ohne Bild")
    await api.confirm_location(event["id"])
    assert (await api.act("organizer-fsi", event["id"], "publish")).status_code == 200
    response = await api.request(None, "GET", FEED)
    SCHEMA.validate(response.json())
    assert response.json()["items"][0]["image"] is None


async def test_filters_order_limit(api: Api) -> None:
    await go_live(
        api, title="B später", startsAt=future(20).isoformat(), endsAt=future(20, 2).isoformat()
    )
    await go_live(
        api, title="A früher", startsAt=future(3).isoformat(), endsAt=future(3, 2).isoformat()
    )
    await go_live(api, user="organizer-makers", org="makers", title="Makers")
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
        await session.execute(text("UPDATE event SET title = 'Geändert' WHERE state = 'published'"))
        await session.commit()
    after = await api.request(None, "GET", FEED, headers={"If-None-Match": etag})
    assert after.status_code == 200 and after.headers["etag"] != etag


async def test_archived_stays_public_and_a_draft_leaves_via_the_view(api: Api) -> None:
    live = await go_live(api)
    async with api.maker() as session:
        await session.execute(text("UPDATE event SET state = 'archived'"))
        await session.commit()
    assert len((await api.request(None, "GET", FEED)).json()["items"]) == 1
    async with api.maker() as session:
        await session.execute(text("UPDATE event SET state = 'draft'"))
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
    ready = await draft_with_poster(api)
    derivative = ready["poster"]["derivatives"]["card1200"]["id"]
    path = f"/api/public/media/{derivative}.webp"
    assert (await api.request(None, "GET", path)).status_code == 404
    await api.act("organizer-fsi", ready["id"], "publish")
    assert (await api.request(None, "GET", path)).status_code == 200
    await api.act("organizer-fsi", ready["id"], "unpublish")
    assert (await api.request(None, "GET", path)).status_code == 404


async def test_a_replaced_poster_gets_a_new_media_id(api: Api) -> None:
    from tests._support.factories import png_bytes

    event = await api.create_event()
    eid = event["id"]
    ids = []
    for color in ("#aa0000", "#00aa00"):
        poster = (await api.upload_poster("organizer-fsi", eid, data=png_bytes(color=color))).json()
        await api.process_poster(poster["id"])
        ids.append(poster["sha256"][:16])
    assert ids[0] != ids[1]


async def test_cancel_and_postpone_stay_in_the_feed_with_their_status(api: Api) -> None:
    live = await go_live(api)
    eid = live["id"]
    cancelled = await api.act(
        "organizer-fsi", eid, "cancel", reason="Intern", publicReasonCode="weather"
    )
    assert cancelled.status_code == 200
    body = (await api.request(None, "GET", FEED)).json()
    SCHEMA.validate(body)
    item = body["items"][0]
    assert item["status"] == "cancelled" and item["statusReason"] == {
        "code": "weather",
        "text": None,
    }
    assert "Intern" not in json.dumps(body)
    await api.act("editor", eid, "reinstate", reason="Doch")
    await api.act("editor", eid, "postpone", reason="Verschoben", publicReasonCode="room")
    item = (await api.request(None, "GET", FEED)).json()["items"][0]
    assert item["status"] == "postponed" and item["statusReason"]["code"] == "room"
    taken = await api.act("editor", eid, "unpublish")
    assert taken.status_code == 200
    assert (await api.request(None, "GET", FEED)).json()["items"] == []


async def test_the_venue_name_comes_from_the_venue_and_a_private_one_is_hidden(api: Api) -> None:
    public = (await api.sql("SELECT id, name FROM venue WHERE NOT is_private AND active LIMIT 1"))[
        0
    ]
    private = (await api.sql("SELECT id FROM venue WHERE slug = 'privat-test' LIMIT 1")) or (
        await api.sql(
            "INSERT INTO venue (slug, name, is_private) VALUES ('privat-test', 'Zuhause', true) "
            "RETURNING id"
        )
    )
    try:
        shown = await go_live(api, venueId=str(public[0]), venueText="Freitext", title="Mit Ort")
        hidden = await go_live(api, venueId=str(private[0][0]), title="Privat")
        items = {i["id"]: i for i in (await api.request(None, "GET", FEED)).json()["items"]}
        assert items[shown["id"]]["venueText"] == public[1]
        assert items[hidden["id"]]["venueText"] is None
        SCHEMA.validate(
            {
                "schema": 2,
                "generatedAt": "2030-01-01T00:00:00Z",
                "nextCursor": None,
                "items": list(items.values()),
            }
        )
    finally:
        await api.sql("UPDATE event SET venue_id = NULL WHERE venue_id = :v", v=private[0][0])
        await api.sql("DELETE FROM venue WHERE id = :v", v=private[0][0])
