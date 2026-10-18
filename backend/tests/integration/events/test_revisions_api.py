"""`GET /events/{id}/revisions` and `/revisions/{rev}`: history, changed fields, access."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def test_the_list_is_newest_first_with_changed_fields(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    await api.patch("organizer-fsi", eid, summary="Neu gefasst", venueText="Aula")
    response = await api.request("organizer-fsi", "GET", f"/api/events/{eid}/revisions")
    page = response.json()
    assert response.status_code == 200 and page["total"] == 3
    revs = page["items"]
    assert [r["rev"] for r in revs] == [3, 2, 1]
    assert set(revs[0]["changedFields"]) == {"summary", "venueText"}
    assert revs[0]["fieldClass"] == "critical" and revs[0]["actorType"] == "human"
    assert revs[0]["actor"]["sub"] == "sub-org-fsi"
    assert set(revs[1]["changedFields"]) == {"state"}
    assert revs[2]["changedFields"] == []
    assert "snapshot" not in revs[0]


async def test_filter_by_class_and_paging(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    await api.patch("organizer-fsi", eid, summary="Text")
    text = (
        await api.request("editor", "GET", f"/api/events/{eid}/revisions?fieldClass=text")
    ).json()
    assert [r["rev"] for r in text["items"]] == [3]
    page = (
        await api.request("editor", "GET", f"/api/events/{eid}/revisions?limit=1&offset=1")
    ).json()
    assert page["total"] == 3 and [r["rev"] for r in page["items"]] == [2]
    bad = await api.request("editor", "GET", f"/api/events/{eid}/revisions?fieldClass=nope")
    assert bad.status_code == 422


async def test_the_detail_has_a_camel_case_snapshot(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    detail = await api.request("organizer-fsi", "GET", f"/api/events/{eid}/revisions/1")
    body = detail.json()
    assert detail.status_code == 200 and body["rev"] == 1
    assert body["snapshot"]["title"] == event["title"] and "startsAt" in body["snapshot"]
    assert body["snapshot"]["state"] == "idea"
    second = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/revisions/2")).json()
    assert second["changedFields"] == ["state"]


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

    from worker.advance import advance_states

    event = await api.to_state("live")
    ends = datetime.fromisoformat(event["endsAt"]) + timedelta(hours=13)
    await advance_states({"advance_sessionmaker": api.maker, "redis": api.pool}, now=ends)
    page = (await api.request("editor", "GET", f"/api/events/{event['id']}/revisions")).json()
    assert page["items"][0]["actorType"] == "system"
    assert page["items"][0]["actor"]["sub"] == "system:advance_states"
