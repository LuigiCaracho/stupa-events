"""Editing by state, optimistic locking, concurrency, slugs, revisions and audit."""

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
                text("SELECT rev, snapshot->>'title' FROM event_revision ORDER BY rev")
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
    assert [tuple(r) for r in revisions] == [(1, "Movienight: Film A"), (2, "Neu")]
    assert actions == ["event_create", "event_update"]
    assert [tuple(s) for s in statuses] == [(None, "draft", "create")]


async def test_stale_rev_is_409_conflict(api: Api) -> None:
    event = await api.create_event()
    ok = await api.request(
        "organizer-fsi", "PATCH", f"/api/events/{event['id']}", json={"rev": 1, "summary": "a"}
    )
    stale = await api.request(
        "organizer-fsi", "PATCH", f"/api/events/{event['id']}", json={"rev": 1, "summary": "b"}
    )
    assert ok.status_code == 200 and stale.status_code == 409 and stale.json()["code"] == "conflict"


async def test_the_archive_is_field_locked_until_restore(api: Api) -> None:
    event = await api.to_state("archived")
    locked = await api.patch("editor", event["id"], title="nein")
    assert locked.status_code == 409 and locked.json()["code"] == "field_locked"
    await api.act("editor", event["id"], "restore")
    assert (await api.patch("editor", event["id"], title="ja")).status_code == 200


async def test_a_published_dossier_is_edited_by_the_organizer_not_the_submitter(
    api: Api,
) -> None:
    event = await api.create_event(user="submitter-fsi")
    await api.act("organizer-fsi", event["id"], "publish")
    assert (await api.patch("submitter-fsi", event["id"], summary="x")).status_code == 403
    assert (await api.patch("organizer-fsi", event["id"], summary="x")).status_code == 200


async def test_actions_in_the_wrong_state_are_409_invalid_state(api: Api) -> None:
    event = await api.create_event()
    for action in ("unpublish", "restore", "cancel"):
        response = await api.act("editor", event["id"], action)
        assert response.status_code == 409 and response.json()["code"] == "invalid_state", action
    again = await api.act("organizer-fsi", event["id"], "publish")
    repeat = await api.act("organizer-fsi", event["id"], "publish")
    assert again.status_code == 200
    assert repeat.status_code == 409 and repeat.json()["code"] == "invalid_state"


async def test_publish_lists_every_missing_field(api: Api) -> None:
    event = await api.create_event()
    await api.sql(
        "UPDATE event SET organization_id = NULL, title = '' WHERE id = :e", e=event["id"]
    )
    response = await api.act("editor", event["id"], "publish")
    body = response.json()
    assert response.status_code == 422 and body["code"] == "publish_incomplete"
    assert {r["field"] for r in body["reasons"]} == {"title", "organizationId"}


async def test_nothing_else_blocks_publishing(api: Api) -> None:
    event = await api.create_event(venueText=None, summary=None, primaryCategoryId=None)
    assert (await api.act("organizer-fsi", event["id"], "publish")).status_code == 200
    past = await api.create_event(
        startsAt=future(-3).isoformat(), endsAt=future(-3, 2).isoformat(), title="Vorbei"
    )
    assert (await api.act("organizer-fsi", past["id"], "publish")).status_code == 200


async def test_concurrent_publishes_exactly_one_wins(api: Api) -> None:
    event = await api.create_event()
    results = await asyncio.gather(
        *(api.act("editor", event["id"], "publish", if_match_rev=event["rev"]) for _ in range(4))
    )
    statuses = sorted(r.status_code for r in results)
    assert statuses.count(200) == 1 and set(statuses) <= {200, 409}
    now = await api.get("editor", event["id"])
    assert now["state"] == "published" and now["rev"] == event["rev"] + 1


async def test_slug_collision_gets_a_suffix_and_slug_is_set_once(api: Api) -> None:
    first = await api.create_event()
    second = await api.create_event()
    slug = (await api.act("editor", first["id"], "publish")).json()["slug"]
    second_slug = (await api.act("editor", second["id"], "publish")).json()["slug"]
    assert second_slug == f"{slug}-2"
    await api.act("editor", second["id"], "unpublish")
    again = await api.act("editor", second["id"], "publish")
    assert again.json()["slug"] == second_slug


async def test_publish_sets_public_seq_and_the_feed_version_once(api: Api) -> None:
    event = await api.create_event()
    published = (await api.act("editor", event["id"], "publish")).json()
    assert published["state"] == "published"
    assert api.pool.counters == {"events:feed:version": 1}
    async with api.maker() as session:
        seq = (await session.execute(text("SELECT public_seq FROM event"))).scalar_one()
    assert seq == 1


async def test_publish_requeues_the_derive_job_when_derivatives_are_missing(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    poster = (await api.upload_poster("organizer-fsi", eid)).json()
    await api.act("editor", eid, "publish")
    assert (
        "derive_poster",
        (poster["id"],),
        {"_job_id": f"derive:{poster['id']}"},
    ) in api.pool.jobs


async def test_audit_chain_verifies_after_the_whole_flow(api: Api) -> None:
    ready = await api.to_state("archived")
    assert ready["state"] == "archived"
    async with api.maker() as session:
        result = await AuditService(session).verify_chain()
        actions = (
            (await session.execute(text("SELECT action FROM audit_entry ORDER BY id")))
            .scalars()
            .all()
        )
    assert result.valid and result.checked == len(actions)
    assert actions.count("event_transition") == 2 and "event_create" in actions


async def test_audit_entries_hold_ids_only(api: Api) -> None:
    ready = await api.to_state("published")
    await api.upload_poster("organizer-fsi", ready["id"])
    async with api.maker() as session:
        rows = (await session.execute(text("SELECT data::text FROM audit_entry"))).scalars().all()
    blob = " ".join(rows)
    assert "Movienight" not in blob and "Kinosaal" not in blob and "Ein Filmplakat" not in blob
