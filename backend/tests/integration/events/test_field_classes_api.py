"""Field classes over HTTP: who changes what in which state (E07)."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def live_event(api: Api, **over: object) -> dict:
    return await api.to_state("live", **over)


async def test_the_organizer_corrects_the_summary_in_live(api: Api) -> None:
    event = await live_event(api)
    seq = (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=event["id"]))[0][0]
    done = await api.patch("organizer-fsi", event["id"], summary="Besserer Kurztext")
    assert done.status_code == 200 and done.json()["rev"] == event["rev"] + 1
    assert done.headers["etag"] == f'"{done.json()["rev"]}"'
    rows = await api.sql(
        "SELECT field_class FROM event_revision WHERE event_id = :i AND rev = :r",
        i=event["id"],
        r=done.json()["rev"],
    )
    assert rows == [("text",)]
    assert (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=event["id"]))[0][
        0
    ] == seq + 1
    assert api.pool.counters.get("events:feed:version", 0) >= 1


async def test_a_description_change_in_live_keeps_public_seq(api: Api) -> None:
    event = await live_event(api)
    seq = (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=event["id"]))[0][0]
    done = await api.patch("organizer-fsi", event["id"], descriptionMd="Längere Beschreibung")
    assert done.status_code == 200
    assert (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=event["id"]))[0][0] == seq


async def test_the_time_is_for_the_editorial_team_only(api: Api) -> None:
    event = await live_event(api)
    moved = future(15).isoformat()
    refused = await api.patch(
        "organizer-fsi", event["id"], startsAt=moved, endsAt=future(15, 2).isoformat()
    )
    assert refused.status_code == 409 and refused.json()["code"] == "field_locked"
    assert {e["field"] for e in refused.json()["errors"]} == {"startsAt", "endsAt"}
    assert (await api.get("editor", event["id"]))["startsAt"] == event["startsAt"]
    seq = (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=event["id"]))[0][0]
    done = await api.patch("editor", event["id"], startsAt=moved, endsAt=future(15, 2).isoformat())
    assert done.status_code == 200
    assert (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=event["id"]))[0][
        0
    ] == seq + 1
    rows = await api.sql(
        "SELECT field_class FROM event_revision WHERE event_id = :i ORDER BY rev DESC LIMIT 1",
        i=event["id"],
    )
    assert rows == [("critical",)]


async def test_an_approver_of_the_own_trusted_org_changes_critical_fields_in_live(api: Api) -> None:
    event = await api.create_event(user="approver-stupa", org="stupa", title="STUPA Fest")
    eid = event["id"]
    await api.fire("approver-stupa", eid, "T01")
    await api.action("editor", eid, "image-exception", reason="Fest ohne Motiv")
    await api.fire("approver-stupa", eid, "T02")
    await api.fire("approver2-stupa", eid, "T04")
    await api.fire("approver2-stupa", eid, "T05")
    done = await api.patch("approver-stupa", eid, venueText="Aula")
    assert done.status_code == 200 and done.json()["venueText"] == "Aula"


async def test_a_title_with_a_status_word_is_refused_in_live(api: Api) -> None:
    event = await live_event(api)
    refused = await api.patch("editor", event["id"], title="[ABGESAGT] Movienight")
    assert refused.status_code == 422 and refused.json()["code"] == "title_has_status"
    assert refused.json()["reasons"][0]["fixAction"] == "mark_cancellation"
    assert (await api.get("editor", event["id"]))["title"] == event["title"]


async def test_a_new_link_host_is_critical(api: Api) -> None:
    event = await live_event(api, descriptionMd="Mehr unter https://example.org/info")
    known = await api.patch(
        "organizer-fsi", event["id"], descriptionMd="Siehe https://example.org/neu"
    )
    assert known.status_code == 200
    fresh = await api.patch("organizer-fsi", event["id"], descriptionMd="https://neu.example.net/x")
    assert fresh.status_code == 409 and fresh.json()["errors"][0]["field"] == "descriptionMd"
    allowed = await api.patch("editor", event["id"], descriptionMd="https://neu.example.net/x")
    assert allowed.status_code == 200
    rows = await api.sql(
        "SELECT field_class FROM event_revision WHERE event_id = :i ORDER BY rev DESC LIMIT 1",
        i=event["id"],
    )
    assert rows == [("critical",)]


async def test_in_review_the_approver_corrects_text_but_the_organizer_cannot(api: Api) -> None:
    event = await api.to_state("in_review")
    eid = event["id"]
    assert (await api.patch("organizer-fsi", eid, summary="x")).status_code == 409
    approver = await api.create_event(user="approver-stupa", org="stupa", title="STUPA Rat")
    await api.fire("approver-stupa", approver["id"], "T01")
    await api.action("editor", approver["id"], "image-exception", reason="Rat ohne Motiv")
    await api.fire("approver-stupa", approver["id"], "T02")
    fixed = await api.patch("approver-stupa", approver["id"], summary="Tippfehler weg")
    assert fixed.status_code == 200
    critical = await api.patch("approver-stupa", approver["id"], title="Neuer Titel")
    assert critical.status_code == 409
    assert (await api.patch("editor", eid, title="Neu")).status_code == 409
    assert (await api.patch("editor", eid, summary="ok")).status_code == 200


@pytest.mark.parametrize("state", ["approved", "followup", "archived", "withdrawn"])
async def test_closed_states_lock_everything(api: Api, state: str) -> None:
    event = await api.to_state("approved")
    if state != "approved":
        await api.sql("UPDATE event SET state = :s WHERE id = :i", s=state, i=event["id"])
    for fields in ({"title": "x"}, {"summary": "x"}):
        response = await api.patch("editor", event["id"], **fields)
        assert response.status_code == 409 and response.json()["code"] == "field_locked"


async def test_mixed_fields_are_all_or_nothing(api: Api) -> None:
    event = await live_event(api)
    response = await api.patch("organizer-fsi", event["id"], summary="Neu", title="Anders")
    assert response.status_code == 409
    again = await api.get("editor", event["id"])
    assert again["summary"] == event["summary"] and again["rev"] == event["rev"]


async def test_a_submitter_is_out_of_live(api: Api) -> None:
    event = await api.create_event(user="submitter-fsi")
    eid = event["id"]
    await api.fire("submitter-fsi", eid, "T01")
    await api.action("editor", eid, "image-exception", reason="Test ohne Motiv")
    await api.fire("organizer-fsi", eid, "T02")
    await api.fire("editor", eid, "T04")
    await api.fire("editor", eid, "T05")
    response = await api.patch("submitter-fsi", eid, summary="x")
    assert response.status_code == 403


async def test_event_out_names_what_the_caller_may_edit(api: Api) -> None:
    event = await live_event(api)
    organizer = await api.get("organizer-fsi", event["id"])
    assert organizer["lockReason"] == "live_critical"
    assert set(organizer["editableFields"]) == {"summary", "descriptionMd", "costText"}
    editor = await api.get("editor", event["id"])
    assert editor["lockReason"] is None and "startsAt" in editor["editableFields"]
    viewer = await api.get("viewer-fsi", event["id"])
    assert viewer["editableFields"] == []


async def test_links_and_cost_text_are_stored_and_validated(api: Api) -> None:
    event = await api.create_event()
    done = await api.patch(
        "organizer-fsi",
        event["id"],
        ticketUrl="https://tickets.example.org/x",
        websiteUrl="https://example.org",
        costText="5 € an der Abendkasse",
    )
    assert done.status_code == 200
    body = done.json()
    assert body["ticketUrl"] == "https://tickets.example.org/x" and body["costText"].startswith("5")
    for bad in ("http://example.org", "https://user@example.org", "https://x", "ftp://a.b"):
        assert (await api.patch("organizer-fsi", event["id"], ticketUrl=bad)).status_code == 422
    cleared = await api.patch("organizer-fsi", event["id"], ticketUrl=None)
    assert cleared.status_code == 200 and cleared.json()["ticketUrl"] is None


async def test_the_list_of_text_changes_and_the_seen_marker(api: Api) -> None:
    event = await live_event(api)
    eid = event["id"]
    await api.patch("organizer-fsi", eid, summary="Neu gefasst")
    tasks = (await api.request("editor", "GET", "/api/tasks")).json()
    assert [c["id"] for c in tasks["changedAfterPublish"]] == [eid]
    entry = tasks["changedAfterPublish"][0]
    assert entry["baselineRev"] == event["publishedRev"]
    assert [c["fieldClass"] for c in entry["changes"]] == ["text"]
    assert tasks["counts"]["changedAfterPublish"] == 1
    own = (await api.request("organizer-fsi", "GET", "/api/tasks")).json()
    assert own["changedAfterPublish"] == []
    seen = await api.action("editor", eid, "acknowledge-changes")
    assert seen.status_code == 200 and seen.json()["textReviewedRev"] > event["rev"]
    again = (await api.request("editor", "GET", "/api/tasks")).json()
    assert again["changedAfterPublish"] == []


async def test_the_editor_does_not_see_the_own_changes(api: Api) -> None:
    event = await live_event(api)
    await api.patch("editor", event["id"], summary="Von der Redaktion")
    tasks = (await api.request("editor", "GET", "/api/tasks")).json()
    assert tasks["changedAfterPublish"] == []


async def test_a_noop_patch_changes_nothing(api: Api) -> None:
    event = await api.create_event()
    response = await api.patch("organizer-fsi", event["id"], title=event["title"])
    assert response.status_code == 200 and response.json()["rev"] == event["rev"]
