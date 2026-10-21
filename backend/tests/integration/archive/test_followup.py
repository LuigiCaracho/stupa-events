"""Follow-up: T09 guards, the outcome, verify-howto, the format hook and the fixture itself."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import Response

from tests.integration.archive.fixture import archived_movienight, ok
from tests.integration.dossier.helpers import seed_principals
from tests.integration.events.harness import Api
from worker.advance import advance_states
from worker.followup import send_followup_reminders

pytestmark = pytest.mark.integration


async def test_the_movienight_fixture_archives_through_t09(api: Api) -> None:
    eid = await archived_movienight(api)
    event = await api.get("organizer-fsi", eid)
    assert event["state"] == "archived" and event["outcome"]["attendance"] == 87
    assert event["format"] == {"slug": "movienight", "title": "Movienight"}
    assert event["howtoVerifiedAt"] is not None and event["howtoUnverified"] is False
    fmt = await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'")
    assert fmt[0][0] is not None


async def followup_event(api: Api) -> dict:
    """A live dossier of `fsi` moved to `followup` by the worker at a fixed clock."""
    event = await api.to_state("live")
    ended = datetime.fromisoformat(event["endsAt"])
    await advance_states(
        {"advance_sessionmaker": api.maker, "redis": api.pool}, now=ended + timedelta(hours=13)
    )
    return await api.get("organizer-fsi", event["id"])


async def test_t09_lists_every_open_part_in_order(api: Api) -> None:
    event = await followup_event(api)
    eid = event["id"]
    await api.sql(
        "INSERT INTO checklist_item (event_id, position, text, phase, required) "
        "VALUES (:e, 'm', 'Abrechnung', 'followup', true)",
        e=eid,
    )
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md) VALUES (:e, 'howto', 'A', 'x')",
        e=eid,
    )
    guards = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/guards/T09")).json()
    assert [r["code"] for r in guards["reasons"]] == [
        "checklist_open",
        "retrospective_missing",
        "outcome_missing",
        "howto_unverified",
    ]
    assert [r["fixAction"] for r in guards["reasons"]] == [
        "open_checklist",
        "fill_retrospective",
        "fill_outcome",
        "verify_howto",
    ]
    assert guards["reasons"][0]["field"] == "followup"
    counts = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/dossier-counts")).json()
    assert counts["followupOpen"] == 4


async def test_a_dossier_without_a_howto_has_nothing_to_verify(api: Api) -> None:
    event = await followup_event(api)
    eid = event["id"]
    await put_outcome(api, eid, {"attendance": 3, "costsCents": 0})
    await ok(
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/documents",
            json={"kind": "retrospective", "bodyMd": "ok"},
        ),
        201,
    )
    archived = await api.fire("organizer-fsi", eid, "T09")
    assert archived.status_code == 200 and archived.json()["howtoUnverified"] is False


async def put_outcome(api: Api, eid: str, body: dict, user: str = "organizer-fsi") -> Response:
    rev = (await api.get("editor", eid))["rev"]
    return await api.request(
        user, "PUT", f"/api/events/{eid}/outcome", json=body, headers={"If-Match": f'"{rev}"'}
    )


async def test_outcome_rules(api: Api) -> None:
    event = await followup_event(api)
    eid = event["id"]
    no_header = await api.request("organizer-fsi", "PUT", f"/api/events/{eid}/outcome", json={})
    assert no_header.status_code == 428
    stale = await api.request(
        "organizer-fsi", "PUT", f"/api/events/{eid}/outcome", json={}, headers={"If-Match": '"1"'}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    bare = await put_outcome(api, eid, {"waived": True})
    assert bare.status_code == 422 and bare.json()["code"] == "waiver_reason_required"
    short = await put_outcome(api, eid, {"waived": True, "waivedReason": "kurz"})
    assert short.status_code == 422
    zero = await put_outcome(api, eid, {"attendance": 0, "costsCents": 0})
    assert zero.status_code == 200 and zero.json()["outcome"]["attendance"] == 0
    waived = await put_outcome(
        api, eid, {"attendance": 9, "waived": True, "waivedReason": "Zahlen wurden nicht erfasst."}
    )
    assert waived.json()["outcome"]["attendance"] is None and waived.json()["outcome"]["waived"]
    viewer = await put_outcome(api, eid, {}, user="viewer-fsi")
    assert viewer.status_code == 403
    stranger = await put_outcome(api, eid, {}, user="organizer-makers")
    assert stranger.status_code == 404
    audit = await api.sql("SELECT data FROM audit_entry WHERE action = 'event_outcome'")
    assert audit and "attendance" not in str(audit)


async def test_the_outcome_is_locked_before_the_end_and_in_planning(api: Api) -> None:
    planning = await api.to_state("planning")
    refused = await put_outcome(api, planning["id"], {"attendance": 1, "costsCents": 0})
    assert refused.status_code == 409 and refused.json()["code"] == "field_locked"
    live = await api.to_state("live")
    early = await put_outcome(api, live["id"], {"attendance": 1, "costsCents": 0})
    assert early.status_code == 409 and early.json()["code"] == "field_locked"


async def test_the_retrospective_is_one_document_with_defaults(api: Api) -> None:
    event = await followup_event(api)
    eid = event["id"]
    created = await ok(
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/documents",
            json={"kind": "retrospective", "bodyMd": "Gut."},
        ),
        201,
    )
    assert created["title"] == "Rückblick" and created["visibility"] == "org"
    assert created["carryOver"] is False
    again = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/documents",
        json={"kind": "retrospective", "bodyMd": "Nochmal."},
    )
    assert again.status_code == 409 and again.json()["code"] == "already_exists"
    early = await api.to_state("planning")
    refused = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{early['id']}/documents",
        json={"kind": "retrospective", "bodyMd": "zu früh"},
    )
    assert refused.status_code == 409 and refused.json()["code"] == "field_locked"


async def test_verify_howto_is_idempotent_reversible_and_dates_the_format_when_archived(
    api: Api,
) -> None:
    event = await followup_event(api)
    eid = event["id"]
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md) VALUES (:e, 'howto', 'A', 'x')",
        e=eid,
    )
    await api.sql("UPDATE event SET format_id = (SELECT id FROM format WHERE slug = 'movienight')")
    first = await ok(
        await api.request("organizer-fsi", "POST", f"/api/events/{eid}/actions/verify-howto")
    )
    second = await ok(
        await api.request("organizer-fsi", "POST", f"/api/events/{eid}/actions/verify-howto")
    )
    assert first["howtoVerifiedAt"] == second["howtoVerifiedAt"] and first["rev"] == second["rev"]
    doc = await api.sql("SELECT verified_by FROM document WHERE event_id = :e", e=eid)
    assert doc[0][0] == "sub-org-fsi"
    undone = await ok(
        await api.request("organizer-fsi", "DELETE", f"/api/events/{eid}/actions/verify-howto")
    )
    assert undone["howtoVerifiedAt"] is None
    again = await ok(
        await api.request("organizer-fsi", "DELETE", f"/api/events/{eid}/actions/verify-howto")
    )
    assert again["rev"] == undone["rev"]
    assert (await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'"))[0][
        0
    ] is None
    await put_outcome(api, eid, {"attendance": 1, "costsCents": 1})
    await ok(
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/documents",
            json={"kind": "retrospective", "bodyMd": "x"},
        ),
        201,
    )
    refused = await api.fire("organizer-fsi", eid, "T09")
    assert refused.json()["code"] == "howto_unverified"
    await api.sql("UPDATE event SET state = 'archived' WHERE id = :e", e=eid)
    late = await ok(
        await api.request("organizer-fsi", "POST", f"/api/events/{eid}/actions/verify-howto")
    )
    assert late["howtoUnverified"] is False
    assert (await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'"))[0][
        0
    ] is not None
    locked = await api.request("organizer-fsi", "DELETE", f"/api/events/{eid}/actions/verify-howto")
    assert locked.status_code == 409 and locked.json()["code"] == "dossier_closed"
    early = await api.to_state("planning")
    wrong_state = await api.request(
        "organizer-fsi", "POST", f"/api/events/{early['id']}/actions/verify-howto"
    )
    assert wrong_state.status_code == 409
    submitter = await api.request("viewer-fsi", "POST", f"/api/events/{eid}/actions/verify-howto")
    assert submitter.status_code == 403


async def test_t09_dates_the_format_and_its_master_howto(api: Api) -> None:
    eid = await archived_movienight(api)
    row = await api.sql("SELECT last_verified_by FROM format WHERE slug = 'movienight'")
    assert row == [("sub-org-fsi",)]
    assert eid


async def test_t09b_archives_after_thirty_days_with_the_mark_and_the_mail(api: Api) -> None:
    await seed_principals(api)
    event = await followup_event(api)
    eid = event["id"]
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md) VALUES (:e, 'howto', 'A', 'x')",
        e=eid,
    )
    await api.sql("UPDATE event SET format_id = (SELECT id FROM format WHERE slug = 'movienight')")
    entered = (await api.sql("SELECT max(at) FROM event_status_event WHERE to_state = 'followup'"))[
        0
    ][0]
    later = entered + timedelta(days=31)
    result = await advance_states({"advance_sessionmaker": api.maker, "redis": api.pool}, now=later)
    assert "archived=1" in result
    archived = await api.get("organizer-fsi", eid)
    assert archived["state"] == "archived" and archived["howtoUnverified"] is True
    assert (await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'"))[0][
        0
    ] is None
    kinds = await api.sql("SELECT kind, params FROM notification WHERE kind = 'auto_archived'")
    assert kinds and kinds[0][1]["howtoUnverified"] is True
    assert set(kinds[0][1]["missing"]) == {"retrospective", "outcome", "howto"}
    sent = [job for job in api.pool.jobs if job[0] == "send_mail"]
    assert sent and "Anleitung" in str(sent[-1])


async def test_t08b_archives_imported_dossiers_without_the_follow_up(api: Api) -> None:
    event = await api.to_state("live")
    await api.sql("UPDATE event SET origin_kind = 'imported' WHERE id = :e", e=event["id"])
    ended = datetime.fromisoformat(event["endsAt"])
    result = await advance_states(
        {"advance_sessionmaker": api.maker, "redis": api.pool}, now=ended + timedelta(hours=13)
    )
    assert "archived=1" in result


async def test_one_reminder_per_entry_and_a_new_one_after_t10(api: Api) -> None:
    await seed_principals(api)
    event = await followup_event(api)
    eid = event["id"]
    ctx = {"redis": api.pool, "followup_sessionmaker": api.maker}
    entered = (await api.sql("SELECT max(at) FROM event_status_event WHERE to_state = 'followup'"))[
        0
    ][0]
    assert "events=0" in await send_followup_reminders(ctx, now=entered + timedelta(days=6))
    first = await send_followup_reminders(ctx, now=entered + timedelta(days=7, hours=1))
    assert "events=1" in first and "mails=1" in first
    second = await send_followup_reminders(ctx, now=entered + timedelta(days=8))
    assert "mails=0" in second
    rows = await api.sql("SELECT count(*) FROM notification WHERE kind = 'followup_reminder'")
    assert rows == [(1,)]
    await api.sql("UPDATE event SET state = 'archived' WHERE id = :e", e=eid)
    reopened = await api.fire("editor", eid, "T10", note="Noch etwas nachtragen")
    assert reopened.json()["state"] == "followup"
    again = (await api.sql("SELECT max(at) FROM event_status_event WHERE to_state = 'followup'"))[
        0
    ][0]
    assert "mails=1" in await send_followup_reminders(ctx, now=again + timedelta(days=7, hours=1))
    assert "skipped" in await send_followup_reminders({"redis": None}, now=again)


async def test_a_foreign_edition_does_not_date_the_master_of_another_organization(
    api: Api,
) -> None:
    event = await followup_event(api)
    eid = event["id"]
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md) VALUES (:e, 'howto', 'A', 'x')",
        e=eid,
    )
    await api.sql(
        "UPDATE event SET state = 'archived', "
        "format_id = (SELECT id FROM format WHERE slug = 'movienight'), "
        "organization_id = (SELECT id FROM organization WHERE slug = 'makers') WHERE id = :e",
        e=eid,
    )
    done = await ok(
        await api.request("organizer-makers", "POST", f"/api/events/{eid}/actions/verify-howto")
    )
    assert done["howtoVerifiedAt"] is not None
    rows = await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'")
    assert rows[0][0] is None
