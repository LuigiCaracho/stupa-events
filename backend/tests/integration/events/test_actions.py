"""cancel, postpone, reinstate, assign-organization, revert-revision, flyer and the M1 alias."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def feed_item(api: Api, eid: str) -> dict | None:
    items = (await api.request(None, "GET", "/api/public/feed/events")).json()["items"]
    return next((i for i in items if i["id"] == eid), None)


async def seq(api: Api, eid: str) -> int:
    return (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=eid))[0][0]


async def test_cancel_keeps_the_event_in_the_feed_as_cancelled(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    before = await seq(api, eid)
    done = await api.action(
        "organizer-fsi", eid, "cancel", reason="Referent krank", publicReasonCode="illness"
    )
    assert done.status_code == 200
    body = done.json()
    assert body["state"] == "live" and body["publicStatus"] == "cancelled"
    assert body["publicReason"] == {"code": "illness", "text": None}
    assert await seq(api, eid) == before + 1
    item = await feed_item(api, eid)
    assert item is not None and item["status"] == "cancelled"
    assert item["statusReason"] == {"code": "illness", "text": None}
    assert "Referent krank" not in str(item)


async def test_the_reason_is_internal_only(api: Api) -> None:
    event = await api.to_state("live")
    await api.action("organizer-fsi", event["id"], "cancel", reason="Geheimer Grund")
    status = await api.sql(
        "SELECT note, transition_id FROM event_status_event WHERE event_id = :i ORDER BY id DESC LIMIT 1",
        i=event["id"],
    )
    assert status == [("Geheimer Grund", "cancel")]
    audit = await api.sql("SELECT data::text FROM audit_entry WHERE action = 'event_cancel'")
    assert "Geheimer Grund" not in audit[0][0]
    revisions = await api.sql(
        "SELECT change_note FROM event_revision WHERE change_note IS NOT NULL"
    )
    assert all("Geheimer" not in (r[0] or "") for r in revisions)


async def test_the_public_text_needs_the_approve_right(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    refused = await api.action(
        "organizer-fsi", eid, "cancel", reason="x", publicReasonText="Der Saal ist belegt"
    )
    assert refused.status_code == 403
    done = await api.action(
        "editor",
        eid,
        "cancel",
        reason="x",
        publicReasonCode="room",
        publicReasonText="Der Saal ist belegt",
    )
    assert done.status_code == 200 and done.json()["publicReason"]["text"] == "Der Saal ist belegt"
    item = await feed_item(api, eid)
    assert item is not None and item["statusReason"]["text"] == "Der Saal ist belegt"


async def test_actions_need_a_reason_and_the_live_state(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    for body in ({}, {"reason": "  "}):
        response = await api.action("organizer-fsi", eid, "cancel", **body)
        assert response.status_code == 422 and response.json()["code"] == "reason_required"
    assert (await api.action("organizer-fsi", eid, "cancel", reason="x")).status_code == 200
    again = await api.action("organizer-fsi", eid, "cancel", reason="x")
    assert again.status_code == 409 and again.json()["code"] == "invalid_transition"
    approved = await api.to_state("approved")
    early = await api.action("editor", approved["id"], "cancel", reason="x")
    assert early.status_code == 409
    bad = await api.action("editor", eid, "postpone", reason="x", publicReasonCode="nonsense")
    assert bad.status_code == 422


async def test_rights_of_the_status_actions(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    assert (await api.action("viewer-fsi", eid, "cancel", reason="x")).status_code == 403
    assert (await api.action("submitter-fsi", eid, "cancel", reason="x")).status_code == 403
    assert (await api.action("organizer-makers", eid, "cancel", reason="x")).status_code == 404
    assert (await api.action("organizer-fsi", eid, "reinstate", reason="x")).status_code == 403
    assert (await api.action("member", eid, "cancel", reason="x")).status_code == 403


async def test_postpone_with_a_new_date_stays_postponed_until_reinstated(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    new_start, new_end = future(30), future(30, 2)
    needs_right = await api.action(
        "organizer-fsi", eid, "postpone", reason="x", newStartsAt=new_start.isoformat()
    )
    assert needs_right.status_code == 403
    done = await api.action(
        "editor",
        eid,
        "postpone",
        reason="Raum belegt",
        publicReasonCode="room",
        newStartsAt=new_start.isoformat(),
        newEndsAt=new_end.isoformat(),
    )
    assert done.status_code == 200 and done.json()["publicStatus"] == "postponed"
    assert done.json()["startsAt"].startswith(new_start.strftime("%Y-%m-%dT%H"))
    item = await feed_item(api, eid)
    assert item is not None and item["status"] == "postponed"
    back = await api.action("editor", eid, "reinstate", reason="Termin steht")
    assert back.status_code == 200 and back.json()["publicStatus"] == "scheduled"
    assert back.json()["publicReason"] is None
    final = await feed_item(api, eid)
    assert final is not None and final["status"] == "scheduled" and final["statusReason"] is None


async def test_postpone_without_a_date_and_its_validation(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    lone = await api.action("editor", eid, "postpone", reason="x", newEndsAt=future(9).isoformat())
    assert lone.status_code == 422
    past = await api.action(
        "editor", eid, "postpone", reason="x", newStartsAt=future(-9).isoformat()
    )
    assert past.status_code == 422 and past.json()["code"] == "start_in_past"
    reversed_ = await api.action(
        "editor",
        eid,
        "postpone",
        reason="x",
        newStartsAt=future(9).isoformat(),
        newEndsAt=future(8).isoformat(),
    )
    assert reversed_.status_code == 422
    plain = await api.action("organizer-fsi", eid, "postpone", reason="Folgt")
    assert plain.status_code == 200 and plain.json()["startsAt"] == event["startsAt"]
    twice = await api.action("organizer-fsi", eid, "postpone", reason="Folgt")
    assert twice.status_code == 409
    cancelled = await api.action("editor", eid, "cancel", reason="Doch nicht")
    assert cancelled.json()["publicStatus"] == "cancelled"


async def test_reinstate_runs_the_publish_guards(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    await api.action("editor", eid, "cancel", reason="x")
    await api.sql("UPDATE event SET title = '[ABGESAGT] Movienight' WHERE id = :i", i=eid)
    refused = await api.action("editor", eid, "reinstate", reason="x")
    assert refused.status_code == 422 and refused.json()["code"] == "title_has_status"
    await api.sql("UPDATE event SET title = 'Movienight' WHERE id = :i", i=eid)
    ok = await api.action("editor", eid, "reinstate", reason="x")
    assert ok.status_code == 200
    plain = await api.action("editor", eid, "reinstate", reason="x")
    assert plain.status_code == 409


async def test_assign_organization(api: Api) -> None:
    proposal = (
        await api.request(
            "member",
            "POST",
            "/api/events",
            json={"title": "Idee", "startsAt": future().isoformat()},
        )
    ).json()
    pid = proposal["id"]
    assert (
        await api.action(
            "organizer-fsi", pid, "assign-organization", organizationId=api.org_ids["fsi"]
        )
    ).status_code == 403
    assert (
        await api.action("member", pid, "assign-organization", organizationId=api.org_ids["fsi"])
    ).status_code == 403
    unknown = await api.action(
        "editor", pid, "assign-organization", organizationId="00000000-0000-0000-0000-000000000000"
    )
    assert unknown.status_code == 404
    done = await api.action("editor", pid, "assign-organization", organizationId=api.org_ids["fsi"])
    assert done.status_code == 200 and done.json()["organization"]["slug"] == "fsi"
    twice = await api.action(
        "editor", pid, "assign-organization", organizationId=api.org_ids["makers"]
    )
    assert twice.status_code == 409 and twice.json()["code"] == "organization_already_set"
    assert (await api.fire("organizer-fsi", pid, "T01")).status_code == 200
    assert (await api.fire("member", pid, "T01")).status_code == 404


async def test_revert_revision_restores_the_content(api: Api) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    first_rev = event["rev"]
    await api.patch("organizer-fsi", eid, summary="Vertippt!!", descriptionMd="Neuer Text")
    reverted = await api.action("editor", eid, "revert-revision", rev=first_rev)
    assert reverted.status_code == 200
    body = reverted.json()
    assert body["summary"] == event["summary"] and body["descriptionMd"] == event["descriptionMd"]
    assert body["rev"] == first_rev + 2 and body["state"] == "live"
    rows = await api.sql(
        "SELECT change_note, field_class FROM event_revision WHERE event_id = :i ORDER BY rev DESC LIMIT 1",
        i=eid,
    )
    assert rows == [(f"Zurückgesetzt auf Revision {first_rev}", "text")]
    assert (await api.action("editor", eid, "revert-revision", rev=999)).status_code == 404
    assert (
        await api.action("organizer-fsi", eid, "revert-revision", rev=first_rev)
    ).status_code == 403


async def test_revert_is_refused_when_the_poster_was_replaced(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    first = await api.upload_poster("organizer-fsi", eid)
    await api.process_poster(first.json()["id"])
    rev_with_poster = (await api.get("editor", eid))["rev"]
    second = await api.upload_poster("organizer-fsi", eid, altText="Anderes Bild")
    assert second.status_code == 201
    refused = await api.action("editor", eid, "revert-revision", rev=rev_with_poster)
    assert refused.status_code == 409 and refused.json()["code"] == "revert_poster_replaced"


async def test_revert_runs_the_live_guards_and_is_closed_after_live(api: Api) -> None:
    event = await api.create_event(summary=None)
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    await api.patch("organizer-fsi", eid, summary="Jetzt mit Kurztext")
    await api.action("editor", eid, "image-exception", reason="Test ohne Motiv")
    await api.fire("organizer-fsi", eid, "T02")
    await api.fire("editor", eid, "T04")
    await api.fire("editor", eid, "T05")
    refused = await api.action("editor", eid, "revert-revision", rev=1)
    assert refused.status_code == 422 and refused.json()["code"] == "field_missing"
    assert (await api.get("editor", eid))["summary"] == "Jetzt mit Kurztext"
    await api.sql("UPDATE event SET state = 'followup' WHERE id = :i", i=eid)
    closed = await api.action("editor", eid, "revert-revision", rev=1)
    assert closed.status_code == 409 and closed.json()["code"] == "field_locked"


async def test_confirm_flyer_and_the_flyer_guard(api: Api) -> None:
    first = await api.to_state("planning")
    poster = await api.upload_poster("organizer-fsi", first["id"])
    await api.process_poster(poster.json()["id"])
    other = await api.to_state(
        "planning",
        title="Anderes Jahr",
        startsAt=future(400).isoformat(),
        endsAt=future(400, 2).isoformat(),
    )
    same_file = await api.upload_poster("organizer-fsi", other["id"])
    await api.process_poster(same_file.json()["id"])
    await api.fire("organizer-fsi", other["id"], "T02")
    guards = (await api.request("editor", "GET", f"/api/events/{other['id']}/guards/T04")).json()
    assert "flyer_date" in [r["code"] for r in guards["reasons"]]
    assert (await api.fire("editor", other["id"], "T04")).json()["code"] == "flyer_date"
    done = await api.action("organizer-fsi", other["id"], "confirm-flyer")
    assert done.status_code == 200 and done.json()["flyerCheckedAt"] is not None
    guards = (await api.request("editor", "GET", f"/api/events/{other['id']}/guards/T04")).json()
    assert "flyer_date" not in [r["code"] for r in guards["reasons"]]
    assert (await api.fire("editor", other["id"], "T04")).status_code == 200
    assert (await api.action("organizer-fsi", other["id"], "confirm-flyer")).status_code == 409
    assert (await api.action("viewer-fsi", first["id"], "confirm-flyer")).status_code == 403
    foreign = await api.create_event(user="submitter2-fsi", title="Fremd")
    assert (await api.action("submitter-fsi", foreign["id"], "confirm-flyer")).status_code == 403


async def test_confirm_flyer_marks_the_poster_and_works_without_one(api: Api) -> None:
    bare = await api.to_state("planning")
    plain = await api.action("organizer-fsi", bare["id"], "confirm-flyer")
    assert plain.status_code == 200 and plain.json()["flyerCheckedAt"] is not None
    event = await api.to_state("planning", title="Mit Plakat")
    poster = (await api.upload_poster("organizer-fsi", event["id"])).json()
    await api.process_poster(poster["id"])
    assert (await api.action("organizer-fsi", event["id"], "confirm-flyer")).status_code == 200
    rows = await api.sql(
        "SELECT flyer_date_confirmed_at IS NOT NULL, flyer_date_confirmed_by FROM attachment WHERE id = :i",
        i=poster["id"],
    )
    assert rows[0][0] is True and rows[0][1]


async def test_acknowledge_changes_needs_live(api: Api) -> None:
    event = await api.to_state("planning")
    refused = await api.action("editor", event["id"], "acknowledge-changes")
    assert refused.status_code == 409
    assert (
        await api.action("organizer-fsi", event["id"], "acknowledge-changes")
    ).status_code == 403


async def test_the_m1_image_exception_path_is_an_alias(api: Api) -> None:
    event = await api.to_state("planning")
    old = await api.request(
        "editor",
        "POST",
        f"/api/events/{event['id']}/image-exception",
        json={"reason": "Alter Pfad ok"},
    )
    new = await api.action("editor", event["id"], "image-exception", reason="Neuer Pfad ist ok")
    assert old.status_code == 200 and new.status_code == 200
    assert new.json()["imageException"]["reason"] == "Neuer Pfad ist ok"
    short = await api.action("editor", event["id"], "image-exception", reason="kurz")
    assert short.status_code == 422


async def test_allowed_actions_and_transitions_in_event_out(api: Api) -> None:
    event = await api.to_state("live")
    editor = await api.get("editor", event["id"])
    assert editor["allowedActions"] == [
        "cancel",
        "postpone",
        "postpone-with-date",
        "public-text",
        "revert-revision",
        "acknowledge-changes",
        "verify-howto",
        "confirm-location",
        "save-as-format",
        "clone",
    ]
    assert editor["allowedTransitions"] == ["T07"]
    organizer = await api.get("organizer-fsi", event["id"])
    assert organizer["allowedActions"] == [
        "cancel",
        "postpone",
        "verify-howto",
        "save-as-format",
        "clone",
    ]
    viewer = await api.get("viewer-fsi", event["id"])
    assert viewer["allowedActions"] == [] and viewer["allowedTransitions"] == []


async def test_a_stale_if_match_on_an_action_is_a_conflict(api: Api) -> None:
    event = await api.to_state("live")
    stale = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{event['id']}/actions/cancel",
        json={"reason": "x"},
        headers={"If-Match": f'"{event["rev"] - 1}"'},
    )
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    assert stale.json()["current"]["rev"] == event["rev"]


async def test_revert_outside_live_and_without_a_summary_change(api: Api) -> None:
    planning = await api.to_state("planning")
    first = planning["rev"]
    await api.patch("organizer-fsi", planning["id"], summary="Anders", title="Neu")
    back = await api.action("editor", planning["id"], "revert-revision", rev=first)
    assert back.status_code == 200 and back.json()["title"] == planning["title"]
    live = await api.to_state("live")
    await api.patch("organizer-fsi", live["id"], descriptionMd="Mehr Text")
    seq = (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=live["id"]))[0][0]
    done = await api.action("editor", live["id"], "revert-revision", rev=live["rev"])
    assert done.status_code == 200
    assert (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=live["id"]))[0][0] == seq
