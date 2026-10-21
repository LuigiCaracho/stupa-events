"""The simplified path through the real API and database: draft, published, archived."""

from __future__ import annotations

import pytest

from app.settings import get_settings
from tests._support.factories import make_settings
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def feed_ids(api: Api) -> list[str]:
    items = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"]
    return [item["id"] for item in items]


async def test_organizer_publishes_with_a_poster_and_archives(api: Api) -> None:
    event = await api.create_event()
    assert event["state"] == "draft" and event["rev"] == 1 and event["createdBy"] == "sub-org-fsi"
    eid = event["id"]
    assert await feed_ids(api) == []
    poster = await api.upload_poster("organizer-fsi", eid)
    assert poster.status_code == 201 and poster.json()["scanStatus"] == "pending"
    assert api.queue.enqueued
    assert await api.process_poster(poster.json()["id"]) == "clean"
    await api.confirm_location(eid)
    published = (await api.act("organizer-fsi", eid, "publish")).json()
    assert published["state"] == "published"
    assert published["slug"].endswith("-movienight-film-a")
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()
    assert [item["id"] for item in feed["items"]] == [eid]
    assert feed["items"][0]["image"]["url"].endswith("-card_1200.webp")
    archived = (await api.act("organizer-fsi", eid, "archive")).json()
    assert archived["state"] == "archived"
    assert await feed_ids(api) == [eid]


async def test_a_dossier_without_a_poster_publishes_and_the_feed_has_no_image(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    published = await api.act("organizer-fsi", eid, "publish")
    assert published.status_code == 200
    await api.confirm_location(eid)
    item = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"][0]
    assert item["id"] == eid and item["image"] is None


async def test_unpublish_leaves_the_feed_and_restore_returns_a_draft(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    assert eid in await feed_ids(api)
    assert (await api.act("organizer-fsi", eid, "unpublish")).json()["state"] == "draft"
    assert await feed_ids(api) == []
    await api.act("organizer-fsi", eid, "publish")
    await api.act("organizer-fsi", eid, "archive")
    denied = await api.act("organizer-fsi", eid, "restore")
    assert denied.status_code == 403
    restored = (await api.act("editor", eid, "restore")).json()
    assert restored["state"] == "draft"
    assert await feed_ids(api) == []


async def test_a_dossier_archived_without_being_public_stays_out_of_feed_and_ics(
    api: Api,
) -> None:
    never = (await api.create_event())["id"]
    await api.act("organizer-fsi", never, "publish")
    await api.act("organizer-fsi", never, "unpublish")
    await api.act("organizer-fsi", never, "archive")
    plain = (await api.create_event())["id"]
    await api.act("organizer-fsi", plain, "archive")
    assert await feed_ids(api) == []
    ics = (await api.request(None, "GET", "/ics/all.ics")).content
    assert never.encode() not in ics and plain.encode() not in ics
    visible = await api.sql("SELECT count(*) FROM public_event_v")
    assert visible == [(0,)]


async def test_a_published_dossier_stays_public_after_the_archive(api: Api) -> None:
    eid = (await api.to_state("published"))["id"]
    await api.act("organizer-fsi", eid, "archive")
    assert await feed_ids(api) == [eid]
    assert (await api.sql("SELECT published_at IS NOT NULL FROM event WHERE id = :e", e=eid)) == [
        (True,)
    ]


async def test_publish_asks_for_title_start_and_organization_only(api: Api) -> None:
    event = await api.create_event()
    await api.sql("UPDATE event SET title = '  ' WHERE id = :e", e=event["id"])
    refused = await api.act("organizer-fsi", event["id"], "publish")
    assert refused.status_code == 422 and refused.json()["code"] == "publish_incomplete"
    assert [r["field"] for r in refused.json()["reasons"]] == ["title"]


async def test_publish_requires_editor_leaves_the_click_to_the_editorial_team(api: Api) -> None:
    api.app.dependency_overrides[get_settings] = lambda: make_settings(publish_requires_editor=True)
    try:
        eid = (await api.create_event())["id"]
        refused = await api.act("organizer-fsi", eid, "publish")
        assert refused.status_code == 403
        assert (await api.act("editor", eid, "publish")).json()["state"] == "published"
    finally:
        del api.app.dependency_overrides[get_settings]
