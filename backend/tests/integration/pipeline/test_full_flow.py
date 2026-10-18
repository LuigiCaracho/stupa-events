"""T00 to T12 through the real API and database, with the worker on a fixed clock."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tests.integration.events.harness import Api, future
from worker.advance import advance_states

pytestmark = pytest.mark.integration

NOTE_TRANSITIONS = ("T03", "T06", "T07", "T10", "T11")


async def run_worker(api: Api, now: datetime) -> str:
    return await advance_states({"advance_sessionmaker": api.maker, "redis": api.pool}, now=now)


async def feed_ids(api: Api) -> list[str]:
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()
    return [item["id"] for item in feed["items"]]


async def test_idea_to_archive_with_every_state_change(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    await api.action("editor", eid, "image-exception", reason="Test ohne Motiv")
    submitted = await api.fire("organizer-fsi", eid, "T02")
    assert submitted.json()["submittedBy"] == "sub-org-fsi"

    returned = await api.fire("editor", eid, "T03", note="Bitte Ort prüfen")
    assert returned.status_code == 200 and returned.json()["state"] == "planning"
    assert returned.json()["submittedBy"] is None and returned.json()["approvedBy"] is None
    assert (await api.fire("organizer-fsi", eid, "T02")).status_code == 200

    approved = (await api.fire("editor", eid, "T04")).json()
    assert approved["state"] == "approved" and approved["slug"]
    back = (await api.fire("editor", eid, "T06", note="Doch noch ändern")).json()
    assert back["state"] == "in_review" and back["approvedBy"] is None
    when = (datetime.fromisoformat(back["startsAt"]) - timedelta(days=1)).isoformat()
    scheduled = (await api.fire("editor", eid, "T04", publishAt=when)).json()
    assert scheduled["publishAt"] is not None and scheduled["publicReason"] is None
    seq_after_t04 = (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=eid))[0][0]
    assert seq_after_t04 == 2

    live = (await api.fire("editor", eid, "T05")).json()
    assert live["state"] == "live" and live["publishedRev"] == live["rev"]
    assert await feed_ids(api) == [eid]
    assert (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=eid))[0][0] == 2

    offline = (await api.fire("editor", eid, "T07", note="Fehler im Text")).json()
    assert offline["state"] == "approved" and offline["publishedRev"] is None
    assert offline["publishAt"] is None
    assert await feed_ids(api) == []
    assert (await api.sql("SELECT public_seq FROM event WHERE id = :i", i=eid))[0][0] == 3
    assert (await api.fire("editor", eid, "T05")).status_code == 200

    ends = datetime.fromisoformat(offline["endsAt"])
    assert await run_worker(api, ends + timedelta(hours=11)) == (
        "published=0 followup=0 archived=0 blocked=0 skipped=0 failed=0"
    )
    assert "followup=1" in await run_worker(api, ends + timedelta(hours=13))
    followup = await api.get("editor", eid)
    assert followup["state"] == "followup"
    assert "followup=0" in await run_worker(api, ends + timedelta(hours=14))
    archived = (await api.fire("organizer-fsi", eid, "T09")).json()
    assert archived["state"] == "archived" and await feed_ids(api) == [eid]
    reopened = await api.fire("editor", eid, "T10", note="Noch etwas nachtragen")
    assert reopened.json()["state"] == "followup"

    rows = await api.sql(
        "SELECT transition_id, actor_type FROM event_status_event WHERE event_id = :i ORDER BY id",
        i=eid,
    )
    assert [r[0] for r in rows] == [
        "T00",
        "T01",
        "T02",
        "T03",
        "T02",
        "T04",
        "T06",
        "T04",
        "T05",
        "T07",
        "T05",
        "T08",
        "T09",
        "T10",
    ]
    assert rows[-3][1] == "system"
    revisions = await api.sql(
        "SELECT rev FROM event_revision WHERE event_id = :i ORDER BY rev", i=eid
    )
    final = await api.get("editor", eid)
    assert [r[0] for r in revisions] == list(range(1, final["rev"] + 1))


async def test_the_worker_run_is_idempotent_and_marks_the_actor_as_system(api: Api) -> None:
    event = await api.to_state("live")
    ends = datetime.fromisoformat(event["endsAt"]) + timedelta(hours=13)
    assert "followup=1" in await run_worker(api, ends)
    assert "followup=0" in await run_worker(api, ends)
    revision = await api.sql(
        "SELECT actor_id, actor_type FROM event_revision WHERE event_id = :i ORDER BY rev DESC LIMIT 1",
        i=event["id"],
    )
    assert revision[0] == ("system:advance_states", "system")
    audit = await api.sql(
        "SELECT actor FROM audit_entry WHERE action = 'event_transition' ORDER BY id DESC LIMIT 1"
    )
    assert audit[0][0] == "system:advance_states"


@pytest.mark.parametrize("tid", NOTE_TRANSITIONS)
async def test_the_mandatory_note_is_a_422_reason_required(api: Api, tid: str) -> None:
    states = {
        "T03": "in_review",
        "T06": "approved",
        "T07": "live",
        "T10": "archived",
        "T11": "idea",
    }
    event = await api.to_state(states[tid] if tid != "T10" else "live")
    if tid == "T10":
        await api.sql("UPDATE event SET state = 'archived' WHERE id = :i", i=event["id"])
    for body in ({}, {"note": "   "}):
        response = await api.fire("editor", event["id"], tid, **body)
        assert response.status_code == 422 and response.json()["code"] == "reason_required"
        assert response.json()["errors"][0]["field"] == "note"
    assert (await api.fire("editor", event["id"], tid, note="Weil es so ist")).status_code == 200


async def test_withdraw_and_restore(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    withdrawn = await api.fire("organizer-fsi", eid, "T11", note="Termin entfällt")
    assert withdrawn.json()["state"] == "withdrawn"
    assert (await api.fire("organizer-fsi", eid, "T12")).status_code == 403
    restored = (await api.fire("editor", eid, "T12")).json()
    assert restored["state"] == "idea"
    note = (await api.sql("SELECT note FROM event_status_event WHERE transition_id = 'T11'"))[0][0]
    assert note == "Termin entfällt"


async def test_publish_at_rules(api: Api) -> None:
    event = await api.to_state("in_review")
    eid = event["id"]
    starts = datetime.fromisoformat(event["startsAt"])
    past = await api.fire("editor", eid, "T04", publishAt=(starts - timedelta(days=99)).isoformat())
    assert past.status_code == 422 and past.json()["code"] == "publish_at_in_past"
    late = await api.fire("editor", eid, "T04", publishAt=(starts + timedelta(days=9)).isoformat())
    assert late.status_code == 422 and late.json()["code"] == "publish_after_end"
    other = await api.fire("editor", eid, "T03", note="x", publishAt=future(2).isoformat())
    assert other.status_code == 422 and other.json()["code"] == "validation_error"
    naive = await api.request(
        "editor",
        "POST",
        f"/api/events/{eid}/transitions/T04",
        json={"publishAt": "2030-01-01T10:00:00"},
    )
    assert naive.status_code == 422


async def test_if_match_on_a_transition(api: Api) -> None:
    event = await api.to_state("idea")
    stale = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{event['id']}/transitions/T01",
        json={},
        headers={"If-Match": '"99"'},
    )
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    assert stale.json()["current"]["id"] == event["id"]
    fresh = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{event['id']}/transitions/T01",
        json={},
        headers={"If-Match": f'"{event["rev"]}"'},
    )
    assert fresh.status_code == 200 and fresh.headers["etag"] == f'"{event["rev"] + 1}"'
    bad = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{event['id']}/transitions/T02",
        json={},
        headers={"If-Match": "abc"},
    )
    assert bad.status_code == 422


async def test_sys_only_transitions_are_forbidden_for_humans_even_for_the_admin(api: Api) -> None:
    event = await api.to_state("live")
    for user in ("editor", "admin"):
        for tid in ("T08", "T08b", "T09b"):
            response = await api.fire(user, event["id"], tid)
            assert response.status_code == 403, (user, tid)
        guards = await api.request(user, "GET", f"/api/events/{event['id']}/guards/T08")
        assert guards.json()["allowed"] is False
        assert guards.json()["reasons"][0]["code"] == "forbidden"
