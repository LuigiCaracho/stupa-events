"""PLAN 5.4, dossier level: who reads a dossier from `idea` to `followup` (404 otherwise)."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def status_of(api: Api, user: str, event_id: str) -> int:
    return (await api.request(user, "GET", f"/api/events/{event_id}")).status_code


@pytest.mark.parametrize("state", ["idea", "planning", "in_review", "live"])
async def test_the_dossier_rows_by_state(api: Api, state: str) -> None:
    event = await api.create_event()
    eid = event["id"]
    if state != "idea":
        await api.fire("organizer-fsi", eid, "T01")
    if state in {"in_review", "live"}:
        await api.request(
            "editor",
            "POST",
            f"/api/events/{eid}/image-exception",
            json={"reason": "Test ohne Motiv"},
        )
        await api.fire("organizer-fsi", eid, "T02")
    if state == "live":
        assert (await api.fire("editor", eid, "T04")).status_code == 200
        assert (await api.fire("editor", eid, "T05")).status_code == 200
    expected = {
        "organizer-fsi": 200,
        "viewer-fsi": 200,
        "editor": 200,
        "admin": 200,
        "stupa": 200,
        "organizer-makers": 404,
        "submitter-ekhg": 404,
        "member": 404,
    }
    assert {user: await status_of(api, user, eid) for user in expected} == expected


async def propose(api: Api, user: str, title: str = "Mein Vorschlag") -> dict:
    response = await api.request(
        user,
        "POST",
        "/api/events",
        json={"title": title, "startsAt": "2030-01-01T10:00:00Z", "endsAt": "2030-01-01T12:00:00Z"},
    )
    assert response.status_code == 201, response.text
    return response.json()


async def test_a_member_reads_their_own_proposal_and_nobody_elses(api: Api) -> None:
    mine = await propose(api, "member")
    assert await status_of(api, "member", mine["id"]) == 200
    assert await status_of(api, "nobody", mine["id"]) == 404
    assert await status_of(api, "organizer-fsi", mine["id"]) == 404
    assert await status_of(api, "editor", mine["id"]) == 200
    listed = (await api.request("member", "GET", "/api/events")).json()["items"]
    assert [e["id"] for e in listed] == [mine["id"]]
    assert (await api.request("nobody", "GET", "/api/events")).json()["items"] == []


async def test_the_proposer_loses_the_dossier_when_an_organization_is_assigned(api: Api) -> None:
    mine = await propose(api, "member")
    done = await api.request(
        "editor",
        "POST",
        f"/api/events/{mine['id']}/actions/assign-organization",
        json={"organizationId": api.org_ids["fsi"]},
    )
    assert done.status_code == 200 and done.json()["organization"]["slug"] == "fsi"
    assert await status_of(api, "member", mine["id"]) == 404
    assert await status_of(api, "organizer-fsi", mine["id"]) == 200
