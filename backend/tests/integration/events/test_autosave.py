"""Autosave (E21): the draft is private, side-effect free and obeys the field locks."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


def put(api: Api, user: str, eid: str, rev: int | None, fields: dict, raw: bytes | None = None):  # noqa: ANN201
    headers = {"If-Match": f'"{rev}"'} if rev is not None else {}
    if raw is not None:
        return api.request(
            user,
            "PUT",
            f"/api/events/{eid}/draft",
            content=raw,
            headers={**headers, "content-type": "application/json"},
        )
    return api.request(
        user, "PUT", f"/api/events/{eid}/draft", json={"fields": fields}, headers=headers
    )


async def counts(api: Api, eid: str) -> tuple:
    rows = await api.sql(
        "SELECT (SELECT count(*) FROM event_revision WHERE event_id = :i), "
        "(SELECT rev FROM event WHERE id = :i), (SELECT public_seq FROM event WHERE id = :i), "
        "(SELECT count(*) FROM audit_entry)",
        i=eid,
    )
    return tuple(rows[0])


async def test_a_draft_changes_nothing_about_the_dossier(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    before = await counts(api, eid)
    response = await put(api, "organizer-fsi", eid, event["rev"], {"summary": "Halber Sat"})
    assert response.status_code == 200
    body = response.json()
    assert body["baseRev"] == event["rev"] and body["fields"] == {"summary": "Halber Sat"}
    assert await counts(api, eid) == before
    again = await put(
        api, "organizer-fsi", eid, event["rev"], {"summary": "Besser", "venueText": "X"}
    )
    assert again.json()["fields"]["summary"] == "Besser"
    got = await api.request("organizer-fsi", "GET", f"/api/events/{eid}/draft")
    assert got.status_code == 200 and got.json()["fields"]["venueText"] == "X"
    assert await counts(api, eid) == before


async def test_a_stale_if_match_is_409_with_the_current_dossier(api: Api) -> None:
    event = await api.to_state("planning")
    await api.patch("organizer-fsi", event["id"], summary="Schneller")
    stale = await put(api, "organizer-fsi", event["id"], event["rev"], {"summary": "x"})
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    assert stale.json()["current"]["summary"] == "Schneller"
    assert stale.json()["currentRev"] == event["rev"] + 1


async def test_critical_fields_cannot_be_parked_in_live(api: Api) -> None:
    event = await api.to_state("live")
    refused = await put(api, "organizer-fsi", event["id"], event["rev"], {"title": "Neu"})
    assert refused.status_code == 409 and refused.json()["code"] == "field_locked"
    text = await put(api, "organizer-fsi", event["id"], event["rev"], {"summary": "Neu"})
    assert text.status_code == 200
    editor = await put(api, "editor", event["id"], event["rev"], {"title": "Neu"})
    assert editor.status_code == 200


async def test_the_draft_belongs_to_its_author(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    await put(api, "organizer-fsi", eid, event["rev"], {"summary": "Meins"})
    for user in ("editor", "admin", "approver-fsi"):
        got = await api.request(user, "GET", f"/api/events/{eid}/draft")
        assert got.status_code == 204, user
    other = await put(api, "editor", eid, event["rev"], {"summary": "Deins"})
    assert other.status_code == 200
    mine = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/draft")).json()
    assert mine["fields"]["summary"] == "Meins"
    gone = await api.request("editor", "DELETE", f"/api/events/{eid}/draft")
    assert gone.status_code == 204
    assert (await api.request("editor", "GET", f"/api/events/{eid}/draft")).status_code == 204
    assert (
        await api.request("organizer-fsi", "GET", f"/api/events/{eid}/draft")
    ).status_code == 200


async def test_a_successful_patch_removes_the_draft(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    await put(api, "organizer-fsi", eid, event["rev"], {"summary": "Entwurf"})
    done = await api.patch("organizer-fsi", eid, summary="Gespeichert")
    assert done.status_code == 200
    assert (
        await api.request("organizer-fsi", "GET", f"/api/events/{eid}/draft")
    ).status_code == 204
    await put(api, "organizer-fsi", eid, done.json()["rev"], {"summary": "Wieder"})
    noop = await api.patch("organizer-fsi", eid, summary="Gespeichert")
    assert noop.status_code == 200
    assert (
        await api.request("organizer-fsi", "GET", f"/api/events/{eid}/draft")
    ).status_code == 204


async def test_preconditions_and_limits(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    assert (await put(api, "organizer-fsi", eid, None, {"summary": "x"})).status_code == 428
    assert (
        await api.request("organizer-fsi", "PATCH", f"/api/events/{eid}", json={"summary": "x"})
    ).status_code == 428
    mismatch = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/events/{eid}",
        json={"rev": event["rev"], "summary": "x"},
        headers={"If-Match": f'"{event["rev"] + 1}"'},
    )
    assert mismatch.status_code == 422
    huge = b'{"fields": {"descriptionMd": "' + b"x" * 70000 + b'"}}'
    assert (await put(api, "organizer-fsi", eid, event["rev"], {}, raw=huge)).status_code == 413
    unknown = await put(api, "organizer-fsi", eid, event["rev"], {"state": "live"})
    assert unknown.status_code == 422
    star = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{eid}/draft",
        json={"fields": {}},
        headers={"If-Match": "*"},
    )
    assert star.status_code == 428


async def test_rights_and_visibility_of_drafts(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    assert (await put(api, "viewer-fsi", eid, event["rev"], {"summary": "x"})).status_code == 403
    assert (
        await put(api, "organizer-makers", eid, event["rev"], {"summary": "x"})
    ).status_code == 404
    assert (await put(api, "member", eid, event["rev"], {"summary": "x"})).status_code == 403
    assert (
        await api.request("organizer-makers", "GET", f"/api/events/{eid}/draft")
    ).status_code == 404
    assert (
        await api.request("organizer-makers", "DELETE", f"/api/events/{eid}/draft")
    ).status_code == 404


async def test_every_event_answer_carries_the_etag(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    for method, url, kw in (
        ("GET", f"/api/events/{eid}", {}),
        ("POST", f"/api/events/{eid}/transitions/T01", {"json": {}}),
        ("PATCH", f"/api/events/{eid}", {"json": {"rev": 2, "summary": "x"}}),
    ):
        response = await api.request("organizer-fsi", method, url, **kw)
        assert response.status_code == 200
        assert response.headers["etag"] == f'"{response.json()["rev"]}"'
    created = await api.request(
        "organizer-fsi",
        "POST",
        "/api/events",
        json={
            "title": "ETag",
            "startsAt": "2030-01-01T10:00:00Z",
            "organizationId": api.org_ids["fsi"],
        },
    )
    assert created.headers["etag"] == '"1"'


async def test_purge_removes_old_drafts_only(api: Api) -> None:
    from worker.advance import purge_drafts

    event = await api.to_state("planning")
    eid = event["id"]
    await put(api, "organizer-fsi", eid, event["rev"], {"summary": "alt"})
    await put(api, "editor", eid, event["rev"], {"summary": "neu"})
    await api.sql(
        "UPDATE editor_draft SET updated_at = now() - interval '15 days' WHERE principal_sub = 'sub-org-fsi'"
    )
    assert await purge_drafts({"advance_sessionmaker": api.maker}) == "purged=1"
    left = await api.sql("SELECT principal_sub FROM editor_draft")
    assert left == [("sub-editor",)]
