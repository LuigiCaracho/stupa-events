"""Proposals (T00 without an organization, E09): quota, withdrawal, hand-over to the editors."""

from __future__ import annotations

import asyncio

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


def body(title: str = "Vorschlag") -> dict[str, object]:
    return {"title": title, "startsAt": future().isoformat()}


async def propose(api: Api, user: str = "member", title: str = "Vorschlag"):  # noqa: ANN201
    return await api.request(user, "POST", "/api/events", json=body(title))


async def test_a_proposal_has_no_organization_and_an_estimated_end(api: Api) -> None:
    response = await propose(api)
    event = response.json()
    assert response.status_code == 201 and event["organization"] is None
    assert event["state"] == "idea" and event["endEstimated"] is True
    starts, ends = event["startsAt"], event["endsAt"]
    assert starts < ends
    explicit = await api.request(
        "member",
        "POST",
        "/api/events",
        json={**body(), "endsAt": future(hours=3).isoformat()},
    )
    assert explicit.json()["endEstimated"] is False


async def test_the_sixth_open_proposal_is_refused(api: Api) -> None:
    for n in range(5):
        assert (await propose(api, title=f"Idee {n}")).status_code == 201
    sixth = await propose(api, title="Zu viel")
    assert sixth.status_code == 422 and sixth.json()["code"] == "proposal_quota_exceeded"
    other = await propose(api, "nobody")
    assert other.status_code == 201


async def test_withdrawing_frees_a_slot(api: Api) -> None:
    ids = [(await propose(api, title=f"Idee {n}")).json()["id"] for n in range(5)]
    assert (await api.fire("member", ids[0], "T11", note="Doch nicht")).status_code == 200
    assert (await propose(api, title="Neu")).status_code == 201


async def test_two_parallel_sixth_proposals_yield_exactly_one(api: Api) -> None:
    for n in range(4):
        await propose(api, title=f"Idee {n}")
    first, second = await asyncio.gather(propose(api, title="A"), propose(api, title="B"))
    assert sorted([first.status_code, second.status_code]) == [201, 422]


async def test_the_proposer_can_only_withdraw(api: Api) -> None:
    pid = (await propose(api)).json()["id"]
    assert (await api.fire("member", pid, "T01")).status_code == 403
    assert (await api.fire("member", pid, "T11")).status_code == 422
    patch = await api.request(
        "member", "PATCH", f"/api/events/{pid}", json={"rev": 1, "summary": "x"}
    )
    assert patch.status_code == 403
    assert (await api.fire("nobody", pid, "T11", note="x")).status_code == 404
    done = await api.fire("member", pid, "T11", note="Zurückgezogen")
    assert done.status_code == 200 and done.json()["state"] == "withdrawn"
    assert done.json()["organization"] is None


async def test_the_editors_complete_and_assign_a_proposal(api: Api) -> None:
    pid = (await propose(api)).json()["id"]
    edited = await api.patch("editor", pid, summary="Von der Redaktion ergänzt")
    assert edited.status_code == 200
    assigned = await api.action(
        "editor", pid, "assign-organization", organizationId=api.org_ids["fsi"]
    )
    assert assigned.status_code == 200
    assert (await api.fire("organizer-fsi", pid, "T01")).status_code == 200


async def test_a_proposal_may_be_withdrawn_after_assignment_only_with_the_org_right(
    api: Api,
) -> None:
    pid = (await propose(api)).json()["id"]
    await api.action("editor", pid, "assign-organization", organizationId=api.org_ids["fsi"])
    assert (await api.fire("member", pid, "T11", note="x")).status_code == 404
    assert (await api.fire("viewer-fsi", pid, "T11", note="x")).status_code == 403
