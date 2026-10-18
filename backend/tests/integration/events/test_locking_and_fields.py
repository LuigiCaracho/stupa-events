"""Field classes by state, optimistic locking, concurrency, revisions and audit."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from app.modules.audit.service import AuditService
from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def test_patch_bumps_rev_and_writes_revision_and_audit(api: Api) -> None:
    event = await api.create_event()
    response = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/events/{event['id']}",
        json={"rev": 1, "title": "Neu", "summary": None},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rev"] == 2 and body["title"] == "Neu" and body["summary"] is None
    async with api.maker() as session:
        revisions = (
            await session.execute(
                text("SELECT rev, field_class, snapshot->>'title' FROM event_revision ORDER BY rev")
            )
        ).all()
        actions = (
            (await session.execute(text("SELECT action FROM audit_entry ORDER BY id")))
            .scalars()
            .all()
        )
        statuses = (
            await session.execute(
                text("SELECT from_state, to_state, transition_id FROM event_status_event")
            )
        ).all()
    assert [tuple(r) for r in revisions] == [
        (1, "state", "Movienight: Film A"),
        (2, "critical", "Neu"),
    ]
    assert actions == ["event_create", "event_update"]
    assert [tuple(s) for s in statuses] == [(None, "idea", "T00")]


async def test_text_only_change_is_classified_as_text(api: Api) -> None:
    event = await api.create_event()
    await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/events/{event['id']}",
        json={"rev": 1, "descriptionMd": "# Hallo"},
    )
    async with api.maker() as session:
        fields = (
            await session.execute(text("SELECT field_class FROM event_revision WHERE rev = 2"))
        ).scalar_one()
    assert fields == "text"


async def test_stale_rev_is_409_conflict(api: Api) -> None:
    event = await api.create_event()
    ok = await api.request(
        "organizer-fsi", "PATCH", f"/api/events/{event['id']}", json={"rev": 1, "summary": "a"}
    )
    stale = await api.request(
        "organizer-fsi", "PATCH", f"/api/events/{event['id']}", json={"rev": 1, "summary": "b"}
    )
    assert ok.status_code == 200 and stale.status_code == 409 and stale.json()["code"] == "conflict"


async def test_states_from_in_review_on_are_field_locked(api: Api) -> None:
    ready = await api.approved_ready_event()
    locked = await api.request(
        "editor",
        "PATCH",
        f"/api/events/{ready['id']}",
        json={"rev": ready["rev"], "title": "nein"},
    )
    assert locked.status_code == 409 and locked.json()["code"] == "field_locked"
    await api.fire("editor", ready["id"], "T04")
    again = await api.request(
        "editor",
        "PATCH",
        f"/api/events/{ready['id']}",
        json={"rev": ready["rev"] + 1, "summary": "x"},
    )
    assert again.json()["code"] == "field_locked"


async def test_invalid_transition_is_409(api: Api) -> None:
    event = await api.create_event()
    response = await api.fire("editor", event["id"], "T04")
    assert response.status_code == 409 and response.json()["code"] == "invalid_transition"
    again = await api.fire("organizer-fsi", event["id"], "T01")
    repeat = await api.fire("organizer-fsi", event["id"], "T01")
    assert again.status_code == 200 and repeat.status_code == 409


async def test_undefined_transitions_are_422(api: Api) -> None:
    event = await api.create_event()
    for tid in ("T00", "T13", "x"):
        response = await api.fire("editor", event["id"], tid)
        assert response.status_code == 422 and response.json()["code"] == "validation_error", tid


async def test_t01_needs_title_start_and_organization_filled(api: Api) -> None:
    event = await api.create_event()
    assert (await api.fire("organizer-fsi", event["id"], "T01")).status_code == 200


async def test_t02_lists_every_missing_field(api: Api) -> None:
    event = await api.create_event(venueText=None, summary=None, primaryCategoryId=None)
    await api.fire("organizer-fsi", event["id"], "T01")
    response = await api.fire("organizer-fsi", event["id"], "T02")
    body = response.json()
    assert response.status_code == 422 and body["code"] == "field_missing"
    assert {r["field"] for r in body["reasons"]} == {"summary", "primaryCategoryId", "venueId"}
    guards = (
        await api.request("organizer-fsi", "GET", f"/api/events/{event['id']}/guards/T02")
    ).json()
    assert guards["allowed"] is False and len(guards["reasons"]) == 3


async def test_past_events_cannot_be_submitted_but_running_ones_can(api: Api) -> None:
    past = await api.create_event(
        startsAt=future(-3).isoformat(), endsAt=future(-3, 2).isoformat(), title="Vorbei"
    )
    await api.fire("organizer-fsi", past["id"], "T01")
    refused = await api.fire("organizer-fsi", past["id"], "T02")
    assert refused.status_code == 422 and refused.json()["code"] == "start_in_past"
    running = await api.create_event(
        startsAt=future(-1).isoformat(), endsAt=future(1).isoformat(), title="Läuft"
    )
    await api.fire("organizer-fsi", running["id"], "T01")
    assert (await api.fire("organizer-fsi", running["id"], "T02")).status_code == 200


async def test_concurrent_approvals_exactly_one_wins(api: Api) -> None:
    ready = await api.approved_ready_event()
    results = await asyncio.gather(
        *(api.fire("editor", ready["id"], "T04", if_match_rev=ready["rev"]) for _ in range(4))
    )
    statuses = sorted(r.status_code for r in results)
    assert statuses.count(200) == 1 and set(statuses) <= {200, 409}
    live = (await api.request("editor", "GET", f"/api/events/{ready['id']}")).json()
    assert live["state"] == "approved" and live["rev"] == ready["rev"] + 1


async def test_slug_collision_gets_a_suffix_and_slug_is_set_once(api: Api) -> None:
    first = await api.approved_ready_event()
    second = await api.approved_ready_event()
    slug = (await api.fire("editor", first["id"], "T04")).json()["slug"]
    second_slug = (await api.fire("editor", second["id"], "T04")).json()["slug"]
    assert second_slug == f"{slug}-2"
    again = await api.fire("editor", second["id"], "T05")
    assert again.json()["slug"] == second_slug


async def test_t04_sets_public_seq_and_after_commit_actions_run_once(api: Api) -> None:
    ready = await api.approved_ready_event()
    approved = (await api.fire("editor", ready["id"], "T04")).json()
    assert approved["state"] == "approved"
    assert api.pool.jobs == []
    await api.fire("editor", ready["id"], "T05")
    assert api.pool.counters == {"events:feed:version": 1}
    async with api.maker() as session:
        seq = (await session.execute(text("SELECT public_seq FROM event"))).scalar_one()
    assert seq == 1


async def test_t04_requeues_the_derive_job_when_derivatives_are_missing(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    poster = (await api.upload_poster("organizer-fsi", eid)).json()
    await api.request(
        "editor",
        "POST",
        f"/api/events/{eid}/image-exception",
        json={"reason": "Notfalls ohne Motiv"},
    )
    await api.fire("organizer-fsi", eid, "T02")
    await api.fire("editor", eid, "T04")
    assert api.pool.jobs == [
        ("derive_poster", (poster["id"],), {"_job_id": f"derive:{poster['id']}"})
    ]


async def test_audit_chain_verifies_after_the_whole_flow(api: Api) -> None:
    ready = await api.approved_ready_event()
    await api.fire("editor", ready["id"], "T04")
    await api.fire("editor", ready["id"], "T05")
    async with api.maker() as session:
        result = await AuditService(session).verify_chain()
        actions = (
            (await session.execute(text("SELECT action FROM audit_entry ORDER BY id")))
            .scalars()
            .all()
        )
    assert result.valid and result.checked == len(actions)
    assert actions.count("event_transition") == 4 and "attachment_upload" in actions
    assert "event_create" in actions and "attachment_scan" in actions


async def test_audit_entries_hold_ids_only(api: Api) -> None:
    ready = await api.approved_ready_event()
    async with api.maker() as session:
        rows = (await session.execute(text("SELECT data::text FROM audit_entry"))).scalars().all()
    blob = " ".join(rows)
    assert "Movienight" not in blob and "Kinosaal" not in blob and "Ein Filmplakat" not in blob
    assert ready["id"]


async def test_status_events_record_the_note(api: Api) -> None:
    event = await api.create_event()
    response = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{event['id']}/transitions/T01",
        json={"note": "Los geht's"},
    )
    assert response.status_code == 200
    too_long = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{event['id']}/transitions/T02",
        json={"note": "x" * 501},
    )
    assert too_long.status_code == 422
    async with api.maker() as session:
        notes = (
            (
                await session.execute(
                    text("SELECT note FROM event_status_event WHERE transition_id = 'T01'")
                )
            )
            .scalars()
            .all()
        )
    assert notes == ["Los geht's"]
