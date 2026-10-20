"""Review fixes of M4: image references, template writes, rescans, rename, locks, recipients."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy import text

import worker.gc as gc
from app.modules.notifications.recipients import recipients_for
from tests._support import samples
from tests._support.factories import png_bytes
from tests._support.memory_storage import MemoryStorage
from tests.integration.dossier.helpers import planning_event, seed_principals, upload
from tests.integration.events.harness import Api
from tests.integration.notifications.conftest import add_member, add_principal, load_event

pytestmark = pytest.mark.integration


async def new_image(api: Api) -> tuple[str, str]:
    response = await api.request(
        "organizer-fsi",
        "POST",
        "/api/media/images",
        files={"file": ("a.png", png_bytes(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"], response.json()["url"]


async def refs_of(api: Api, image_id: str) -> set[tuple[str, str]]:
    rows = await api.sql(
        "SELECT owner_type, owner_id::text FROM media_ref WHERE image_id = :i", i=UUID(image_id)
    )
    return {(r[0], r[1]) for r in rows}


async def test_a_comment_image_is_referenced_and_survives_the_gc(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    eid = await planning_event(api)
    image_id, path = await new_image(api)
    response = await api.request(
        "editor", "POST", f"/api/events/{eid}/comments", json={"bodyMd": f"Siehe ![x]({path})"}
    )
    assert response.status_code == 201, response.text
    assert await refs_of(api, image_id) == {("comment", response.json()["id"])}
    storage = MemoryStorage()
    key = (await api.sql("SELECT storage_key FROM markdown_image"))[0][0]
    storage.blobs[key] = b"x"
    await api.sql("UPDATE markdown_image SET created_at = :c", c=datetime(2026, 1, 1, tzinfo=UTC))
    monkeypatch.setattr(gc, "utcnow", lambda: datetime(2026, 7, 20, 3, 50, tzinfo=UTC))
    ctx: dict[str, Any] = {"gc_sessionmaker": api.maker, "object_storage": storage}
    assert "marked=0" in await gc.gc_media(ctx)
    monkeypatch.setattr(gc, "utcnow", lambda: datetime(2026, 7, 22, 3, 50, tzinfo=UTC))
    assert "swept=0" in await gc.gc_media(ctx)
    assert key in storage.blobs


async def test_new_dossiers_and_event_drafts_reference_their_images(api: Api) -> None:
    image_id, path = await new_image(api)
    event = await api.create_event(descriptionMd=f"![y]({path})")
    assert await refs_of(api, image_id) == {("event", event["id"])}
    other_id, other_path = await new_image(api)
    eid = event["id"]
    rev = (await api.get("editor", eid))["rev"]
    draft = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{eid}/draft",
        json={"fields": {"descriptionMd": f"![z]({other_path})"}},
        headers={"If-Match": f'"{rev}"'},
    )
    assert draft.status_code == 200, draft.text
    assert {t for t, _ in await refs_of(api, other_id)} == {"draft"}
    deleted = await api.request("organizer-fsi", "DELETE", f"/api/events/{eid}/draft")
    assert deleted.status_code == 204
    assert await refs_of(api, other_id) == set()


async def test_a_mail_template_is_not_writable_through_the_generic_route(api: Api) -> None:
    eid = await planning_event(api)
    created = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/events/{eid}/mail-templates/new",
        json={"title": "Einladung", "subject": "Hallo", "bodyMd": "Hallo {{ event.title }}"},
    )
    assert created.status_code == 201, created.text
    response = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/documents/{created.json()['id']}",
        json={"bodyMd": "{{ nope.field }}"},
        headers={"If-Match": '"1"'},
    )
    assert response.status_code == 409 and response.json()["code"] == "use_mail_templates"


async def test_the_document_put_has_a_body_cap(api: Api) -> None:
    eid = await planning_event(api)
    doc = (
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/documents",
            json={"kind": "notes", "title": "N", "bodyMd": "a"},
        )
    ).json()
    response = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/documents/{doc['id']}",
        content=b'{"bodyMd": "' + b"a" * (2 * 1024 * 1024) + b'"}',
        headers={"If-Match": '"1"', "Content-Type": "application/json"},
    )
    assert response.status_code == 413


async def test_required_template_items_stay_required_and_viewers_are_no_assignees(
    api: Api,
) -> None:
    await seed_principals(api)
    eid = await planning_event(api)
    await api.request(
        "organizer-fsi", "POST", f"/api/events/{eid}/checklist/apply-template", json={}
    )
    data = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/checklist")).json()
    required = next(i for i in data["items"] if i["required"])
    patched = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/checklist-items/{required['id']}",
        json={"required": False},
    )
    assert patched.status_code == 409 and patched.json()["code"] == "template_item"
    free = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/checklist/items",
        json={"text": "Frei", "phase": "live", "required": True},
    )
    item = free.json()["id"]
    toggled = await api.request(
        "organizer-fsi", "PATCH", f"/api/checklist-items/{item}", json={"required": False}
    )
    assert toggled.status_code == 200
    audit = await api.sql("SELECT data::text FROM audit_entry WHERE data::text LIKE '%required%'")
    assert audit and "True" in audit[-1][0]
    viewer = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/checklist-items/{item}",
        json={"assigneeSub": "sub-view-fsi"},
    )
    assert viewer.status_code == 422 and viewer.json()["code"] == "assignee_not_member"


async def test_a_stuck_scan_can_be_repeated_and_a_dead_queue_does_not_fail_the_upload(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    eid = await planning_event(api)

    async def broken(attachment_id: UUID) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(api.queue, "enqueue", broken)
    quote = await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())
    assert quote.status_code == 201, quote.text
    url = f"/api/attachments/{quote.json()['id']}/rescan"
    fresh = await api.request("editor", "POST", url)
    assert fresh.status_code == 409
    await api.sql("UPDATE attachment SET created_at = :c", c=datetime.now(UTC) - timedelta(hours=1))
    monkeypatch.undo()
    stuck = await api.request("editor", "POST", url)
    assert stuck.status_code == 202
    assert UUID(quote.json()["id"]) in api.queue.enqueued


async def test_requeue_stale_scans_picks_up_old_pending_rows(api: Api) -> None:
    from tests.integration.events.harness import FakePool
    from worker.scan import requeue_stale_scans

    eid = await planning_event(api)
    old = (await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())).json()
    await upload(api, "organizer-fsi", eid, "quote", "b.pdf", samples.pdf_bytes())
    await api.sql(
        "UPDATE attachment SET created_at = :c WHERE id = :i",
        c=datetime.now(UTC) - timedelta(hours=1),
        i=UUID(old["id"]),
    )
    pool = FakePool()
    ctx = {"files_sessionmaker": api.maker, "redis": pool}
    assert await requeue_stale_scans(ctx) == 1
    assert [(job[0], job[1][0]) for job in pool.jobs] == [("scan_attachment", old["id"])]


async def test_a_replacement_decides_the_depicted_persons_and_a_rename_keeps_the_extension(
    api: Api,
) -> None:
    eid = await planning_event(api)
    first = (
        await upload(
            api,
            "organizer-fsi",
            eid,
            "social_post",
            "a.png",
            png_bytes(),
            meta='{"channel": "instagram"}',
            altText="Bild",
            credit="Ada",
            rightsBasis="own_work",
            personsDepicted="true",
            consentNote="Einverständnis liegt vor",
        )
    ).json()
    replace = f"/api/attachments/{first['id']}/replace"
    files = {"file": ("b.png", png_bytes(), "image/png")}
    kept = (await api.request("organizer-fsi", "POST", replace, files=files)).json()
    assert kept["personsDepicted"] is True
    off = await api.request(
        "organizer-fsi", "POST", replace, files=files, data={"personsDepicted": "false"}
    )
    assert off.status_code == 201 and off.json()["personsDepicted"] is False
    assert off.json()["consentNote"] is None
    bad = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/attachments/{off.json()['id']}",
        json={"displayName": "virus.exe"},
    )
    assert bad.status_code == 422 and bad.json()["code"] == "extension_changed"
    good = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/attachments/{off.json()['id']}",
        json={"displayName": "neu.png"},
    )
    assert good.status_code == 200 and good.json()["displayName"] == "neu.png"


async def test_parallel_selections_in_one_group_never_break_the_unique_index(api: Api) -> None:
    eid = await planning_event(api)
    ids = []
    for vendor in ("A", "B", "C"):
        row = await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/quotes",
            json={"grp": "Technik", "vendor": vendor, "amountCents": 100},
        )
        ids.append(row.json()["id"])
    results = await asyncio.gather(
        *(api.request("organizer-fsi", "POST", f"/api/quotes/{i}/select") for i in ids)
    )
    assert [r.status_code for r in results] == [200, 200, 200]
    assert (await api.sql("SELECT count(*) FROM quote WHERE selected"))[0][0] == 1


async def test_comment_added_only_reaches_people_who_still_read_the_dossier(api: Api) -> None:
    await seed_principals(api)
    eid = await planning_event(api)
    for _ in range(2):
        await api.request(
            "organizer-makers", "POST", f"/api/events/{eid}/comments", json={"bodyMd": "x"}
        )
    async with api.maker() as session:
        gone = await add_principal(session, "sub-gone")
        await add_member(session, gone, api.org_ids["fsi"], "submitter")
        await session.execute(
            text(
                "INSERT INTO comment (event_id, author_sub, body_md) VALUES (:e, 'sub-gone', 'x'),"
                " (:e, 'sub-org-makers', 'y')"
            ),
            {"e": UUID(eid)},
        )
        row = await load_event(session, eid)
        before = await recipients_for(session, "comment_added", row, None)
        assert "sub-gone" in before and "sub-org-makers" not in before
        await session.execute(
            text("DELETE FROM membership WHERE principal_id = :p"),
            {"p": gone.id},
        )
        after = await recipients_for(session, "comment_added", row, None)
        assert "sub-gone" not in after


async def test_prefs_flag_kinds_without_mail_and_item_text_stays_out_of_params(api: Api) -> None:
    prefs = (await api.request("organizer-fsi", "GET", "/api/account/notification-prefs")).json()
    flags = {p["kind"]: p["mailAvailable"] for p in prefs["items"]}
    assert flags["comment_added"] is True and flags["comment_resolved"] is False
    assert next(p for p in prefs["items"] if p["kind"] == "comment_resolved")["mail"] is False
    await seed_principals(api)
    eid = await planning_event(api)
    await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/checklist/items",
        json={"text": "Geheimer Text", "phase": "live", "assigneeSub": "sub-sub-fsi"},
    )
    rows = await api.sql("SELECT params::text FROM notification WHERE kind = 'task_assigned'")
    assert rows and "Geheimer" not in rows[0][0]


async def test_comment_threads_on_a_restricted_file_are_hidden_from_others(api: Api) -> None:
    await seed_principals(api)
    eid = await planning_event(api)
    quote = (await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())).json()
    posted = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/comments",
        json={"bodyMd": "Zu teuer", "anchor": {"attachmentId": quote["id"]}},
    )
    assert posted.status_code == 201, posted.text
    as_viewer = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/comments")).json()
    as_editor = (await api.request("editor", "GET", f"/api/events/{eid}/comments")).json()
    assert as_viewer == [] and len(as_editor) == 1
