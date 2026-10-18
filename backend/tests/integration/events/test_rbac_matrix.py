"""Role x {own organization, foreign organization} x endpoint (5.5)."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration

OPS = ("read", "listed", "create", "patch", "T01", "T02", "T04", "poster", "exception")
ALL_OK = dict(read=200, listed=True, create=201, patch=200, T01=200, T02=200, T04=200)
ALL_OK |= dict(poster=201, exception=200)
NO_WRITE = dict(read=200, listed=True, create=403, patch=403, T01=403, T02=403, T04=403)
NO_WRITE |= dict(poster=403, exception=403)
FOREIGN_WITH_GATE = dict(read=404, listed=False, create=404, patch=404, T01=404, T02=404)
FOREIGN_WITH_GATE |= dict(T04=404, poster=404, exception=403)
NO_ORG = dict(read=404, listed=False, create=403, patch=403, T01=403, T02=403, T04=403)
NO_ORG |= dict(poster=403, exception=403)
ORGANIZER = ALL_OK | dict(T04=403, exception=403)

# Role x relation to the fsi dossier x operation, exact (PLAN 5.5, contract M2 6.2).
MATRIX: dict[str, dict[str, int | bool]] = {
    "admin": ALL_OK,
    "editor": ALL_OK,
    "stupa": NO_WRITE,
    "organizer-fsi": ORGANIZER,
    "approver-fsi": ORGANIZER,
    "submitter-fsi": NO_WRITE | dict(create=201),
    "viewer-fsi": NO_WRITE,
    "organizer-makers": FOREIGN_WITH_GATE,
    "approver-stupa": FOREIGN_WITH_GATE,
    "submitter-ekhg": FOREIGN_WITH_GATE,
    "member": NO_ORG,
    "nobody": NO_ORG,
}


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


async def observed(api: Api, user: str) -> dict[str, int | bool]:
    """Run every operation of `OPS` as `user` on fresh fsi dossiers; return the outcomes."""
    idea = {n: await event_in(api, "idea", f"Idee {n}") for n in ("a", "b", "c", "d")}
    planning = await event_in(api, "planning", "Zur Einreichung")
    review = await event_in(api, "in_review", "Zur Freigabe")
    a = idea["a"]
    listing = (await api.request(user, "GET", "/api/events")).json()["items"]
    return {
        "read": (await api.request(user, "GET", f"/api/events/{a['id']}")).status_code,
        "listed": a["id"] in [e["id"] for e in listing],
        "create": (await api.request(user, "POST", "/api/events", json=body(api))).status_code,
        "patch": (
            await api.request(
                user, "PATCH", f"/api/events/{a['id']}", json={"rev": a["rev"], "summary": "neu"}
            )
        ).status_code,
        "T01": (await api.fire(user, idea["b"]["id"], "T01")).status_code,
        "T02": (await api.fire(user, planning["id"], "T02")).status_code,
        "T04": (await api.fire(user, review["id"], "T04")).status_code,
        "poster": (await api.upload_poster(user, idea["c"]["id"])).status_code,
        "exception": (
            await api.request(
                user,
                "POST",
                f"/api/events/{idea['d']['id']}/image-exception",
                json={"reason": "Test ohne Motiv"},
            )
        ).status_code,
    }


@pytest.mark.parametrize("user", MATRIX)
async def test_role_by_organization_by_operation(api: Api, user: str) -> None:
    assert await observed(api, user) == MATRIX[user]


@pytest.mark.parametrize("user", [u for u, row in MATRIX.items() if row["read"] == 404])
async def test_a_foreign_dossier_does_not_exist_for_the_caller(api: Api, user: str) -> None:
    eid = (await api.create_event(user="organizer-fsi"))["id"]
    guards_gate = MATRIX[user]["T01"]
    for url, want in [
        (f"/api/events/{eid}", 404),
        (f"/api/events/{eid}/guards/T01", guards_gate),
        (f"/api/events/{eid}/poster/file", 404),
    ]:
        response = await api.request(user, "GET", url)
        assert response.status_code == want, (user, url)
        assert response.json()["code"] == ("not_found" if want == 404 else "forbidden")


async def test_the_partner_account_gets_404_on_foreign_dossiers_and_guards(api: Api) -> None:
    eid = (await api.create_event(user="organizer-fsi"))["id"]
    for transition in ("T01", "T02", "T04", "T05"):
        assert (await api.fire("submitter-ekhg", eid, transition)).status_code == 404
        guards = await api.request(
            "submitter-ekhg", "GET", f"/api/events/{eid}/guards/{transition}"
        )
        assert guards.status_code == 404
    own = await api.create_event(user="submitter-ekhg", org="ekhg", title="Partnerfest")
    listed = (await api.request("submitter-ekhg", "GET", "/api/events")).json()["items"]
    assert [e["id"] for e in listed] == [own["id"]]


async def test_create_in_a_foreign_organization_is_404_for_an_org_member(api: Api) -> None:
    response = await api.request("organizer-makers", "POST", "/api/events", json=body(api, "fsi"))
    assert response.status_code == 404 and response.json()["code"] == "not_found"


async def test_a_viewer_creates_nowhere(api: Api) -> None:
    for org in ("fsi", "makers"):
        response = await api.request("viewer-fsi", "POST", "/api/events", json=body(api, org))
        assert response.status_code == 403 and response.json()["code"] == "forbidden"


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
    await api.add_user("mapped", {"Campus-Gruppe": ("approver", "makers")})
    made = await api.request("mapped", "POST", "/api/events", json=body(api, "makers"))
    assert made.status_code == 201
    unmapped = await api.request("organizer-fsi", "POST", "/api/events", json=body(api, "makers"))
    assert unmapped.status_code == 404
