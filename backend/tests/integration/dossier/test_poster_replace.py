"""Replacing the poster of a published dossier: the old one stays until the new one is clean."""

from __future__ import annotations

import pytest

from tests._support.factories import png_bytes
from tests.integration.dossier.helpers import live_event
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def test_poster_replace_live_swaps_after_scan_and_derivatives(api: Api) -> None:
    live = await live_event(api)
    eid, old = live["id"], live["poster"]["id"]
    seq_before = (await api.sql("SELECT public_seq FROM event"))[0][0]
    revisions_before = (await api.sql("SELECT count(*) FROM event_revision"))[0][0]
    forbidden = await api.upload_poster("organizer-fsi", eid, data=png_bytes(1500, 900))
    assert forbidden.status_code == 403
    response = await api.upload_poster("editor", eid, data=png_bytes(1500, 900))
    assert response.status_code == 201, response.text
    new = response.json()
    assert new["supersedesId"] == old
    now = await api.get("editor", eid)
    assert now["poster"]["id"] == old and now["poster"]["retiredAt"] is None
    assert (await api.sql("SELECT public_seq FROM event"))[0][0] == seq_before
    assert await api.process_poster(new["id"]) == "clean"
    swapped = await api.get("editor", eid)
    assert swapped["poster"]["id"] == new["id"]
    rows = await api.sql("SELECT id::text, retired_at IS NOT NULL FROM attachment")
    assert {r[0]: r[1] for r in rows} == {old: True, new["id"]: False}
    assert (await api.sql("SELECT public_seq FROM event"))[0][0] == seq_before + 1
    last = (
        await api.sql(
            "SELECT field_class, change_note, actor_id FROM event_revision ORDER BY id DESC LIMIT 1"
        )
    )[0]
    assert tuple(last) == ("critical", "Poster ersetzt", "system:promote_poster")
    assert (await api.sql("SELECT count(*) FROM event_revision"))[0][0] == revisions_before + 1
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"]
    item = next(i for i in feed if i["id"] == eid)
    assert new["sha256"][:16] in item["image"]["url"]


async def test_an_infected_replacement_leaves_the_published_poster_alone(api: Api) -> None:
    live = await live_event(api)
    eid, old = live["id"], live["poster"]["id"]
    new = (await api.upload_poster("editor", eid, data=png_bytes(1500, 900))).json()
    assert await api.process_poster(new["id"], signature="Eicar-Test-Signature") == "infected"
    now = await api.get("editor", eid)
    assert now["poster"]["id"] == old and now["state"] == "live"
    listed = (await api.request("editor", "GET", f"/api/events/{eid}/attachments")).json()
    assert {a["id"]: a["scanStatus"] for a in listed} == {old: "clean", new["id"]: "infected"}
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"]
    assert any(i["id"] == eid for i in feed)


async def test_the_promote_job_is_idempotent_and_ignores_stale_replacements(api: Api) -> None:
    live = await live_event(api)
    eid = live["id"]
    first = (await api.upload_poster("editor", eid, data=png_bytes(1500, 900))).json()
    assert await api.process_poster(first["id"]) == "clean"
    seq = (await api.sql("SELECT public_seq FROM event"))[0][0]
    assert await api.process_poster(first["id"]) == "clean"
    assert (await api.get("editor", eid))["poster"]["id"] == first["id"]
    assert (await api.sql("SELECT public_seq FROM event"))[0][0] == seq


async def test_the_review_state_swaps_the_hero_at_once(api: Api) -> None:
    event = await api.approved_ready_event()
    eid = event["id"]
    new = (await api.upload_poster("editor", eid, data=png_bytes(1500, 900))).json()
    now = await api.get("editor", eid)
    assert now["poster"]["id"] == new["id"] and now["poster"]["scanStatus"] == "pending"
    old = await api.request("editor", "GET", f"/api/events/{eid}/attachments?includeRetired=true")
    assert sum(1 for a in old.json() if a["retiredAt"]) == 1
