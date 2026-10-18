"""Role x {own organization, foreign organization} x endpoint (5.5)."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration

# user: (create, read, patch someone else's dossier, submit T02, approve T04)
OWN_ORG = {
    "viewer-fsi": (403, 200, 403, 403, 403),
    "submitter-fsi": (201, 200, 403, 403, 403),
    "organizer-fsi": (201, 200, 200, 200, 403),
    "approver-fsi": (201, 200, 200, 200, 403),
    "editor": (201, 200, 200, 200, 200),
}
FOREIGN = ["organizer-makers", "nobody"]


def body(api: Api, org: str = "fsi") -> dict[str, object]:
    return {
        "title": "Event",
        "startsAt": future().isoformat(),
        "endsAt": future(hours=2).isoformat(),
        "organizationId": api.org_ids[org],
    }


async def event_in(api: Api, state: str, title: str) -> dict:
    """An event made by the organizer, moved to `planning` or `in_review` (with exception)."""
    event = await api.create_event(user="organizer-fsi", title=title)
    eid = event["id"]
    if state == "idea":
        return event
    await api.fire("organizer-fsi", eid, "T01")
    if state == "in_review":
        await api.request(
            "editor",
            "POST",
            f"/api/events/{eid}/image-exception",
            json={"reason": "Test ohne Motiv"},
        )
        await api.fire("organizer-fsi", eid, "T02")
    return (await api.request("editor", "GET", f"/api/events/{eid}")).json()


@pytest.mark.parametrize("user", OWN_ORG)
async def test_own_organization(api: Api, user: str) -> None:
    create, read, patch, submit, approve = OWN_ORG[user]
    seed = await event_in(api, "idea", "Gelesen und geändert")
    assert (await api.request(user, "POST", "/api/events", json=body(api))).status_code == create
    assert (await api.request(user, "GET", f"/api/events/{seed['id']}")).status_code == read
    patched = await api.request(
        user, "PATCH", f"/api/events/{seed['id']}", json={"rev": seed["rev"], "summary": "neu"}
    )
    assert patched.status_code == patch
    planning = await event_in(api, "planning", "Zur Einreichung")
    assert (await api.fire(user, planning["id"], "T02")).status_code == submit
    in_review = await event_in(api, "in_review", "Zur Freigabe")
    assert (await api.fire(user, in_review["id"], "T04")).status_code == approve


@pytest.mark.parametrize("user", FOREIGN)
async def test_foreign_organization_is_invisible(api: Api, user: str) -> None:
    seed = await api.create_event(user="organizer-fsi")
    eid = seed["id"]
    for method, url, kw in [
        ("GET", f"/api/events/{eid}", {}),
        ("PATCH", f"/api/events/{eid}", {"json": {"rev": 1, "summary": "x"}}),
        ("POST", f"/api/events/{eid}/transitions/T01", {"json": {}}),
        ("GET", f"/api/events/{eid}/guards/T01", {}),
        ("GET", f"/api/events/{eid}/poster/file", {}),
    ]:
        response = await api.request(user, method, url, **kw)
        assert response.status_code in {403, 404}, (method, url)
    upload = await api.upload_poster(user, eid)
    assert upload.status_code in {403, 404}
    listed = (await api.request(user, "GET", "/api/events")).json()
    assert eid not in [e["id"] for e in listed["items"]]
    created = await api.request(user, "POST", "/api/events", json=body(api, "fsi"))
    assert created.status_code in {403, 404}


async def test_create_in_a_foreign_organization_is_404_for_an_org_member(api: Api) -> None:
    response = await api.request("organizer-makers", "POST", "/api/events", json=body(api, "fsi"))
    assert response.status_code == 404 and response.json()["code"] == "not_found"


async def test_unauthenticated_is_401_everywhere(api: Api) -> None:
    for method, url in [
        ("GET", "/api/events"),
        ("POST", "/api/events"),
        ("GET", "/api/categories"),
    ]:
        assert (await api.request(None, method, url)).status_code == 401


async def test_submitter_works_on_own_dossiers_only(api: Api) -> None:
    mine = await api.create_event(user="submitter-fsi")
    theirs = await api.create_event(user="submitter2-fsi", title="Fremdes")
    patch = {"rev": 1, "summary": "geändert"}
    assert (
        await api.request("submitter-fsi", "PATCH", f"/api/events/{mine['id']}", json=patch)
    ).status_code == 200
    assert (
        await api.request("submitter-fsi", "PATCH", f"/api/events/{theirs['id']}", json=patch)
    ).status_code == 403
    assert (await api.fire("submitter-fsi", mine["id"], "T01")).status_code == 200
    assert (await api.fire("submitter-fsi", theirs["id"], "T01")).status_code == 403
    assert (await api.upload_poster("submitter-fsi", theirs["id"])).status_code == 403
    assert (await api.upload_poster("submitter-fsi", mine["id"])).status_code == 201
    assert (await api.fire("submitter-fsi", mine["id"], "T02")).status_code == 403


async def test_untrusted_org_approver_cannot_approve_but_trusted_can(api: Api) -> None:
    fsi = await api.approved_ready_event()
    assert (await api.fire("approver-fsi", fsi["id"], "T04")).status_code == 403
    stupa = await api.create_event(user="editor", org="stupa", title="STUPA Sitzung")
    await api.fire("editor", stupa["id"], "T01")
    await api.upload_poster("editor", stupa["id"])
    await api.request(
        "editor",
        "POST",
        f"/api/events/{stupa['id']}/image-exception",
        json={"reason": "Sitzung ohne Motiv"},
    )
    await api.fire("editor", stupa["id"], "T02")
    assert (await api.fire("approver-stupa", stupa["id"], "T04")).status_code == 200


async def test_group_mapping_row_grants_a_role(api: Api) -> None:
    from sqlalchemy import text

    async with api.maker() as session:
        await session.execute(
            text(
                "INSERT INTO group_mapping (oidc_group, role, organization_id) "
                "SELECT 'events-fsi-organizer', 'approver', id FROM organization WHERE slug = 'makers'"
            )
        )
        await session.commit()
    made = await api.request("organizer-fsi", "POST", "/api/events", json=body(api, "makers"))
    assert made.status_code == 201
