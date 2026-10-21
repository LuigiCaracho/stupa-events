"""The documentation after the event: the archive worker, outcome, retrospective and the howto mark."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import Response

from tests.integration.archive.fixture import archived_movienight, ok
from tests.integration.events.harness import Api
from worker.advance import archive_ended

pytestmark = pytest.mark.integration


def worker_ctx(api: Api) -> dict:
    return {"advance_sessionmaker": api.maker, "redis": api.pool}


async def ended_event(api: Api) -> dict:
    return await api.to_state("published")


async def after_end(api: Api, event: dict, hours: int = 13) -> str:
    ended = datetime.fromisoformat(event["endsAt"])
    return await archive_ended(worker_ctx(api), now=ended + timedelta(hours=hours))


async def put_outcome(api: Api, eid: str, body: dict, user: str = "organizer-fsi") -> Response:
    rev = (await api.get("editor", eid))["rev"]
    return await api.request(
        user, "PUT", f"/api/events/{eid}/outcome", json=body, headers={"If-Match": f'"{rev}"'}
    )


async def test_the_movienight_fixture_archives_through_the_worker(api: Api) -> None:
    eid = await archived_movienight(api)
    event = await api.get("organizer-fsi", eid)
    assert event["state"] == "archived" and event["outcome"]["attendance"] == 87
    assert event["format"] == {"slug": "movienight", "title": "Movienight"}
    assert event["howtoVerifiedAt"] is not None and event["howtoUnverified"] is False
    fmt = await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'")
    assert fmt[0][0] is not None


async def test_the_worker_archives_twelve_hours_after_the_end_and_not_before(api: Api) -> None:
    event = await ended_event(api)
    assert await after_end(api, event, hours=11) == "archived=0 failed=0"
    assert (await api.get("editor", event["id"]))["state"] == "published"
    assert await after_end(api, event, hours=13) == "archived=1 failed=0"
    assert (await api.get("editor", event["id"]))["state"] == "archived"
    assert await after_end(api, event, hours=14) == "archived=0 failed=0"


async def test_the_worker_leaves_drafts_alone_and_archives_a_cancelled_event(api: Api) -> None:
    draft = await api.create_event(title="Nie veröffentlicht")
    cancelled = await api.to_state("published", title="Abgesagt")
    await api.act("organizer-fsi", cancelled["id"], "cancel", reason="x", publicReasonCode="other")
    assert await after_end(api, cancelled) == "archived=1 failed=0"
    assert (await api.get("editor", draft["id"]))["state"] == "draft"
    archived = await api.get("editor", cancelled["id"])
    assert archived["state"] == "archived" and archived["publicStatus"] == "cancelled"


async def test_the_worker_revision_and_status_name_the_system_actor(api: Api) -> None:
    event = await ended_event(api)
    await after_end(api, event)
    status = await api.sql(
        "SELECT transition_id, actor_type, from_state, to_state FROM event_status_event "
        "ORDER BY id DESC LIMIT 1"
    )
    assert status == [("archive", "system", "published", "archived")]


async def test_outcome_rules(api: Api) -> None:
    event = await ended_event(api)
    eid = event["id"]
    no_header = await api.request("organizer-fsi", "PUT", f"/api/events/{eid}/outcome", json={})
    assert no_header.status_code == 428
    stale = await api.request(
        "organizer-fsi", "PUT", f"/api/events/{eid}/outcome", json={}, headers={"If-Match": '"1"'}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    bare = await put_outcome(api, eid, {"waived": True})
    assert bare.status_code == 200 and bare.json()["outcome"]["waivedReason"] is None
    long_reason = await put_outcome(api, eid, {"waived": True, "waivedReason": "x" * 301})
    assert long_reason.status_code == 422
    zero = await put_outcome(api, eid, {"attendance": 0, "costsCents": 0})
    assert zero.status_code == 200 and zero.json()["outcome"]["attendance"] == 0
    waived = await put_outcome(
        api, eid, {"attendance": 9, "waived": True, "waivedReason": "Zahlen wurden nicht erfasst."}
    )
    assert waived.json()["outcome"]["attendance"] is None and waived.json()["outcome"]["waived"]
    assert (await put_outcome(api, eid, {}, user="viewer-fsi")).status_code == 403
    assert (await put_outcome(api, eid, {}, user="organizer-makers")).status_code == 404
    audit = await api.sql("SELECT data FROM audit_entry WHERE action = 'event_outcome'")
    assert audit and "attendance" not in str(audit)


async def test_the_outcome_is_open_in_every_state(api: Api) -> None:
    draft = await api.create_event()
    assert (
        await put_outcome(api, draft["id"], {"attendance": 1, "costsCents": 0})
    ).status_code == 200
    archived = await api.to_state("archived")
    late = await put_outcome(api, archived["id"], {"attendance": 5, "costsCents": 10})
    assert late.status_code == 200 and late.json()["state"] == "archived"


async def test_the_retrospective_is_one_document_with_defaults_in_every_state(api: Api) -> None:
    event = await api.to_state("archived")
    eid = event["id"]
    path = f"/api/events/{eid}/documents"
    created = await ok(
        await api.request(
            "organizer-fsi", "POST", path, json={"kind": "retrospective", "bodyMd": "Gut."}
        ),
        201,
    )
    assert created["title"] == "Rückblick" and created["visibility"] == "org"
    assert created["carryOver"] is False
    again = await api.request(
        "organizer-fsi", "POST", path, json={"kind": "retrospective", "bodyMd": "Nochmal."}
    )
    assert again.status_code == 409 and again.json()["code"] == "already_exists"
    early = await api.create_event()
    first = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{early['id']}/documents",
        json={"kind": "retrospective", "bodyMd": "vorab"},
    )
    assert first.status_code == 201


async def test_the_archive_stays_open_for_the_documentation_but_not_for_the_frame(
    api: Api,
) -> None:
    event = await api.to_state("archived")
    eid = event["id"]
    note = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/documents",
        json={"kind": "notes", "title": "Nachtrag", "bodyMd": "Hausmeister war pünktlich."},
    )
    assert note.status_code == 201
    comment = await api.request(
        "organizer-fsi", "POST", f"/api/events/{eid}/comments", json={"bodyMd": "Danke"}
    )
    assert comment.status_code == 201
    item = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/checklist/items",
        json={"text": "Abrechnung", "phase": "followup"},
    )
    assert item.status_code == 201
    quote = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/quotes",
        json={"grp": "Technik", "vendor": "Licht GmbH", "amountCents": 100},
    )
    assert quote.status_code == 201
    locked = await api.patch("organizer-fsi", eid, title="Neu")
    assert locked.status_code == 409 and locked.json()["code"] == "field_locked"
    status = await api.act("organizer-fsi", eid, "cancel", reason="x", publicReasonCode="other")
    assert status.status_code == 409 and status.json()["code"] == "invalid_state"


async def test_verify_howto_is_idempotent_reversible_and_dates_the_format(api: Api) -> None:
    event = await ended_event(api)
    eid = event["id"]
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md) VALUES (:e, 'howto', 'A', 'x')",
        e=eid,
    )
    await api.sql("UPDATE event SET format_id = (SELECT id FROM format WHERE slug = 'movienight')")
    url = f"/api/events/{eid}/actions/verify-howto"
    first = await ok(await api.request("organizer-fsi", "POST", url))
    second = await ok(await api.request("organizer-fsi", "POST", url))
    assert first["howtoVerifiedAt"] == second["howtoVerifiedAt"] and first["rev"] == second["rev"]
    doc = await api.sql("SELECT verified_by FROM document WHERE event_id = :e", e=eid)
    assert doc[0][0] == "sub-org-fsi"
    undone = await ok(await api.request("organizer-fsi", "DELETE", url))
    assert undone["howtoVerifiedAt"] is None
    again = await ok(await api.request("organizer-fsi", "DELETE", url))
    assert again["rev"] == undone["rev"]
    await ok(await api.request("organizer-fsi", "POST", url))
    assert (await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'"))[0][
        0
    ] is not None
    await after_end(api, event)
    locked = await api.request("organizer-fsi", "DELETE", url)
    assert locked.status_code == 409 and locked.json()["code"] == "invalid_state"
    early = await api.create_event()
    wrong_state = await api.request(
        "organizer-fsi", "POST", f"/api/events/{early['id']}/actions/verify-howto"
    )
    assert wrong_state.status_code == 409
    assert (await api.request("viewer-fsi", "POST", url)).status_code == 403


async def test_archiving_dates_nothing_by_itself(api: Api) -> None:
    event = await ended_event(api)
    await api.sql("UPDATE event SET format_id = (SELECT id FROM format WHERE slug = 'movienight')")
    await after_end(api, event)
    archived = await api.get("organizer-fsi", event["id"])
    assert archived["state"] == "archived"
    assert (await api.sql("SELECT last_verified_at FROM format WHERE slug = 'movienight'"))[0][
        0
    ] is None


async def test_a_foreign_edition_does_not_date_the_master_of_another_organization(
    api: Api,
) -> None:
    event = await ended_event(api)
    eid = event["id"]
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md) VALUES (:e, 'howto', 'A', 'x')",
        e=eid,
    )
    await api.sql(
        "UPDATE event SET state = 'archived', published_at = now(), "
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


async def test_the_worker_skips_vanished_and_changed_dossiers_and_survives_a_failure(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    from uuid import UUID, uuid4

    import worker.advance as advance

    maker = api.maker
    assert await advance.archive_one(maker, api.pool, uuid4()) == "skipped"
    draft = await api.create_event()
    assert await advance.archive_one(maker, api.pool, UUID(draft["id"])) == "skipped"
    event = await ended_event(api)

    async def broken(*_args: object) -> str:
        raise RuntimeError("down")

    monkeypatch.setattr(advance, "archive_one", broken)
    assert await after_end(api, event) == "archived=0 failed=1"
