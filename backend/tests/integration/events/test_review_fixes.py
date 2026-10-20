"""Findings of the M3 review: locked revert, live guards on text, links, mandatory If-Match."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("state", ["in_review", "approved"])
async def test_revert_is_closed_in_the_review_states(api: Api, state: str) -> None:
    event = await api.to_state("planning")
    eid, first = event["id"], event["rev"]
    await api.patch("organizer-fsi", eid, title="Neuer Titel")
    await api.action("editor", eid, "image-exception", reason="Test ohne Motiv")
    await api.fire("organizer-fsi", eid, "T02")
    if state == "approved":
        assert (await api.fire("editor", eid, "T04")).status_code == 200
    refused = await api.action("editor", eid, "revert-revision", rev=first)
    assert refused.status_code == 409 and refused.json()["code"] == "field_locked"
    assert (await api.get("editor", eid))["title"] == "Neuer Titel"
    assert "revert-revision" not in (await api.get("editor", eid))["allowedActions"]


async def test_a_live_summary_cannot_be_emptied(api: Api) -> None:
    event = await api.to_state("live")
    refused = await api.patch("organizer-fsi", event["id"], summary=None)
    assert refused.status_code == 422 and refused.json()["code"] == "field_missing"
    assert (await api.get("editor", event["id"]))["summary"] == event["summary"]


@pytest.mark.parametrize(
    "text",
    [
        "[x](//evil.example)",
        "<a href='//evil.example/x'>x</a>",
        "ftp://evil.example/a",
        "evil.example/a",
    ],
)
async def test_a_new_external_host_in_live_text_is_critical(api: Api, text: str) -> None:
    event = await api.to_state("live")
    refused = await api.patch("organizer-fsi", event["id"], descriptionMd=text)
    assert refused.status_code == 409 and refused.json()["code"] == "field_locked"
    allowed = await api.patch("editor", event["id"], descriptionMd=text)
    assert allowed.status_code == 200


@pytest.mark.parametrize(
    ("kind", "name", "body"),
    [
        ("fire", "T05", {}),
        ("action", "cancel", {"reason": "x", "publicReasonCode": "other"}),
        ("action", "postpone", {"reason": "x", "publicReasonCode": "other"}),
        ("action", "reinstate", {"reason": "x"}),
        ("action", "revert-revision", {"rev": 1}),
    ],
)
async def test_decisions_need_an_if_match(api: Api, kind: str, name: str, body: dict) -> None:
    event = await api.to_state("approved" if name == "T05" else "live")
    call = api.fire if kind == "fire" else api.action
    response = await call("editor", event["id"], name, without_if_match=True, **body)
    assert response.status_code == 428
    star = await api.request(
        "editor",
        "POST",
        f"/api/events/{event['id']}/{'transitions' if kind == 'fire' else 'actions'}/{name}",
        json=body,
        headers={"If-Match": "*"},
    )
    assert star.status_code == 428


async def test_approving_a_stale_version_conflicts(api: Api) -> None:
    event = await api.to_state("in_review")
    stale = event["rev"]
    await api.patch("editor", event["id"], summary="Korrigiert")
    response = await api.request(
        "editor",
        "POST",
        f"/api/events/{event['id']}/transitions/T04",
        json={},
        headers={"If-Match": f'"{stale}"'},
    )
    assert response.status_code == 409 and response.json()["code"] == "conflict"


async def test_postpone_into_another_year_runs_the_flyer_guard(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    poster = await api.upload_poster("organizer-fsi", eid)
    await api.process_poster(poster.json()["id"])
    await api.fire("organizer-fsi", eid, "T02")
    assert (await api.fire("editor", eid, "T04")).status_code == 200
    assert (await api.fire("editor", eid, "T05")).status_code == 200
    other = await api.create_event(title="Zweiter Termin")
    again = await api.upload_poster("organizer-fsi", other["id"])
    await api.process_poster(again.json()["id"])
    moved = await api.action(
        "editor",
        eid,
        "postpone",
        reason="Nächstes Jahr",
        publicReasonCode="other",
        newStartsAt=future(400).isoformat(),
        newEndsAt=future(400, 2).isoformat(),
    )
    assert moved.status_code == 422 and moved.json()["code"] == "flyer_date"
    assert (await api.get("editor", eid))["publicStatus"] == "scheduled"


async def test_change_notes_and_review_people_stay_internal(api: Api) -> None:
    event = await api.to_state("in_review")
    eid = event["id"]
    await api.add_open_comment(eid)
    await api.fire("editor", eid, "T03", note="Bitte Ort prüfen")
    await api.fire("organizer-fsi", eid, "T02")
    await api.fire("editor", eid, "T04")
    await api.fire("editor", eid, "T05")
    inside = (await api.request("editor", "GET", f"/api/events/{eid}/revisions")).json()
    assert any(r["changeNote"] for r in inside["items"])
    detail = (await api.request("editor", "GET", f"/api/events/{eid}/revisions/1")).json()
    assert "createdBy" in detail["snapshot"]
    outside = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/revisions")).json()
    assert all(r["changeNote"] is None for r in outside["items"])
    masked = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/revisions/1")).json()
    for key in ("imageException", "createdBy", "submittedBy", "approvedBy"):
        assert key not in masked["snapshot"]


async def test_a_chunked_draft_body_is_capped_before_it_is_read(api: Api) -> None:
    event = await api.to_state("planning")

    async def chunks():  # noqa: ANN202
        for _ in range(100):
            yield b"x" * 1024

    response = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{event['id']}/draft",
        content=chunks(),
        headers={"If-Match": f'"{event["rev"]}"', "content-type": "application/json"},
    )
    assert response.status_code == 413


async def test_approval_needs_the_required_fields_again(api: Api) -> None:
    event = await api.to_state("in_review")
    emptied = await api.patch("editor", event["id"], summary=None)
    assert emptied.status_code in {200, 422}
    if emptied.status_code == 200:
        refused = await api.fire("editor", event["id"], "T04")
        assert refused.status_code == 422 and refused.json()["code"] == "field_missing"


async def test_the_plan_lock_alone_also_closes_a_revert(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.modules.pipeline import revert

    monkeypatch.setattr(revert, "REVERTIBLE", (*revert.REVERTIBLE, "approved"))
    event = await api.to_state("planning")
    eid = event["id"]
    await api.patch("organizer-fsi", eid, title="Neuer Titel")
    await api.action("editor", eid, "image-exception", reason="Test ohne Motiv")
    await api.fire("organizer-fsi", eid, "T02")
    assert (await api.fire("editor", eid, "T04")).status_code == 200
    refused = await api.action("editor", eid, "revert-revision", rev=event["rev"])
    assert refused.status_code == 409 and refused.json()["code"] == "field_locked"
