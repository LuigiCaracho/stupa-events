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


@pytest.mark.xfail(strict=True, reason="M3 proposals: a member reads their own proposal")
async def test_a_member_reads_their_own_proposal(api: Api) -> None:
    proposal = await api.request(
        "member",
        "POST",
        "/api/events",
        json={
            "title": "Mein Vorschlag",
            "startsAt": "2030-01-01T10:00:00Z",
            "endsAt": "2030-01-01T12:00:00Z",
        },
    )
    assert proposal.status_code == 201
    assert await status_of(api, "member", proposal.json()["id"]) == 200
