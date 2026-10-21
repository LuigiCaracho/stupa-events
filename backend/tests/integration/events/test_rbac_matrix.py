"""Role x {own organization, foreign organization} x endpoint (5.5)."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration

OPS = ("read", "listed", "create", "patch", "publish", "archive", "poster")
ALL_OK = dict(read=200, listed=True, create=201, patch=200, publish=200, archive=200, poster=201)
NO_WRITE = dict(read=200, listed=True, create=404, patch=403, publish=403, archive=403, poster=403)
FOREIGN = dict(read=404, listed=False, create=404, patch=404, publish=404, archive=404, poster=404)
NO_RIGHT = FOREIGN | dict(publish=403, archive=403)
NO_ORG = NO_RIGHT | dict(patch=403, poster=403)

# Role x relation to the fsi dossier x operation, exact (PLAN 5.5, contract M5b 4.2).
MATRIX: dict[str, dict[str, int | bool]] = {
    "admin": ALL_OK,
    "editor": ALL_OK,
    "stupa": NO_WRITE,
    "organizer-fsi": ALL_OK,
    "submitter-fsi": NO_WRITE | dict(create=201),
    "viewer-fsi": NO_WRITE,
    "organizer-makers": FOREIGN,
    "submitter-ekhg": NO_RIGHT,
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


async def observed(api: Api, user: str) -> dict[str, int | bool]:
    """Run every operation of `OPS` as `user` on fresh fsi dossiers; return the outcomes."""
    drafts = {n: await api.create_event(user="organizer-fsi", title=f"Idee {n}") for n in "abcd"}
    a = drafts["a"]
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
        "publish": (await api.act(user, drafts["b"]["id"], "publish")).status_code,
        "archive": (await api.act(user, drafts["d"]["id"], "archive")).status_code,
        "poster": (await api.upload_poster(user, drafts["c"]["id"])).status_code,
    }


@pytest.mark.parametrize("user", MATRIX)
async def test_role_by_organization_by_operation(api: Api, user: str) -> None:
    assert await observed(api, user) == MATRIX[user]


@pytest.mark.parametrize("user", [u for u, row in MATRIX.items() if row["read"] == 404])
async def test_a_foreign_dossier_does_not_exist_for_the_caller(api: Api, user: str) -> None:
    eid = (await api.create_event(user="organizer-fsi"))["id"]
    for url in (
        f"/api/events/{eid}",
        f"/api/events/{eid}/poster/file",
        f"/api/events/{eid}/revisions",
    ):
        response = await api.request(user, "GET", url)
        assert response.status_code == 404, (user, url)
        assert response.json()["code"] == "not_found"


async def test_a_foreign_organizer_gets_404_and_a_partner_without_the_right_403(api: Api) -> None:
    eid = (await api.create_event(user="organizer-fsi"))["id"]
    for action in ("publish", "unpublish", "archive", "cancel"):
        assert (await api.act("organizer-makers", eid, action, if_match_rev=1)).status_code == 404
        assert (await api.act("submitter-ekhg", eid, action, if_match_rev=1)).status_code == 403
    own = await api.create_event(user="submitter-ekhg", org="ekhg", title="Partnerfest")
    listed = (await api.request("submitter-ekhg", "GET", "/api/events")).json()["items"]
    assert [e["id"] for e in listed] == [own["id"]]


async def test_create_in_a_foreign_organization_is_404_for_an_org_member(api: Api) -> None:
    response = await api.request("organizer-makers", "POST", "/api/events", json=body(api, "fsi"))
    assert response.status_code == 404 and response.json()["code"] == "not_found"


async def test_a_viewer_creates_in_no_organization_and_a_dossier_needs_one(api: Api) -> None:
    for org in ("fsi", "makers"):
        response = await api.request("viewer-fsi", "POST", "/api/events", json=body(api, org))
        assert response.status_code == 404 and response.json()["code"] == "not_found"
    bare = {"title": "Vorschlag", "startsAt": future().isoformat()}
    assert (await api.request("viewer-fsi", "POST", "/api/events", json=bare)).status_code == 422


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
    assert (await api.act("submitter-fsi", mine["id"], "publish")).status_code == 403
    assert (await api.upload_poster("submitter-fsi", theirs["id"])).status_code == 403
    assert (await api.upload_poster("submitter-fsi", mine["id"])).status_code == 201


async def test_a_publish_policy_can_bind_publishing_to_the_editorial_team(api: Api) -> None:
    from app.settings import get_settings
    from tests._support.factories import make_settings

    app = api.client._transport.app  # type: ignore[attr-defined]
    app.dependency_overrides[get_settings] = lambda: make_settings(publish_requires_editor=True)
    mine = await api.create_event(user="organizer-fsi")
    refused = await api.act("organizer-fsi", mine["id"], "publish")
    assert refused.status_code == 403
    assert (await api.act("editor", mine["id"], "publish")).status_code == 200


async def test_group_mapping_row_grants_a_role(api: Api) -> None:
    await api.add_user("mapped", {"Campus-Gruppe": ("organizer", "makers")})
    made = await api.request("mapped", "POST", "/api/events", json=body(api, "makers"))
    assert made.status_code == 201
    unmapped = await api.request("organizer-fsi", "POST", "/api/events", json=body(api, "makers"))
    assert unmapped.status_code == 404


async def test_a_reader_of_the_dossier_who_publishes_elsewhere_gets_403_not_404(api: Api) -> None:
    await api.add_user(
        "split", {"makers-team": ("organizer", "makers"), "fsi-readers": ("viewer", "fsi")}
    )
    eid = (await api.create_event(user="organizer-fsi"))["id"]
    refused = await api.act("split", eid, "publish")
    assert refused.status_code == 403
