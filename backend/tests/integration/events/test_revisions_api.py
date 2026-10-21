"""`GET /events/{id}/revisions` and `/revisions/{rev}`: history, changed fields, access."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def test_the_list_is_newest_first_with_changed_fields(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.patch("organizer-fsi", eid, summary="Neu gefasst", venueText="Aula")
    await api.act("organizer-fsi", eid, "publish")
    response = await api.request("organizer-fsi", "GET", f"/api/events/{eid}/revisions")
    page = response.json()
    assert response.status_code == 200 and page["total"] == 3
    revs = page["items"]
    assert [r["rev"] for r in revs] == [3, 2, 1]
    assert "state" in revs[0]["changedFields"] and "slug" in revs[0]["changedFields"]
    assert set(revs[1]["changedFields"]) == {"summary", "venueText"}
    assert revs[0]["actorType"] == "human" and "fieldClass" not in revs[0]
    assert revs[0]["actor"]["sub"] == "sub-org-fsi"
    assert revs[2]["changedFields"] == []
    assert "snapshot" not in revs[0]


async def test_paging(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.patch("organizer-fsi", eid, summary="Text")
    await api.patch("organizer-fsi", eid, summary="Zweiter Text")
    page = (
        await api.request("editor", "GET", f"/api/events/{eid}/revisions?limit=1&offset=1")
    ).json()
    assert page["total"] == 3 and [r["rev"] for r in page["items"]] == [2]


async def test_the_detail_has_a_camel_case_snapshot(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.act("organizer-fsi", eid, "publish")
    detail = await api.request("organizer-fsi", "GET", f"/api/events/{eid}/revisions/1")
    body = detail.json()
    assert detail.status_code == 200 and body["rev"] == 1
    assert body["snapshot"]["title"] == event["title"] and "startsAt" in body["snapshot"]
    assert body["snapshot"]["state"] == "draft"
    second = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/revisions/2")).json()
    assert "state" in second["changedFields"]


async def test_missing_revisions_and_foreign_dossiers_are_404(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    assert (
        await api.request("editor", "GET", f"/api/events/{eid}/revisions/99")
    ).status_code == 404
    for user in ("organizer-makers", "member", "nobody"):
        assert (await api.request(user, "GET", f"/api/events/{eid}/revisions")).status_code == 404
        assert (await api.request(user, "GET", f"/api/events/{eid}/revisions/1")).status_code == 404
    assert (await api.request(None, "GET", f"/api/events/{eid}/revisions")).status_code == 401


async def test_the_worker_revision_names_the_system_actor(api: Api) -> None:
    from datetime import datetime, timedelta

    from worker.advance import archive_ended

    event = await api.to_state("published")
    ends = datetime.fromisoformat(event["endsAt"]) + timedelta(hours=13)
    await archive_ended({"advance_sessionmaker": api.maker, "redis": api.pool}, now=ends)
    page = (await api.request("editor", "GET", f"/api/events/{event['id']}/revisions")).json()
    assert page["items"][0]["actorType"] == "system"
    assert page["items"][0]["actor"]["sub"] == "system:archive_ended"
