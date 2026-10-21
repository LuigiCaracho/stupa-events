"""Clone, preview and "last time" on the Movienight fixture (M5 acceptance a)."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest

from tests.integration.archive.fixture import archived_movienight, ok
from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def master_howto(api: Api, source: str) -> None:
    await ok(
        await api.request(
            "editor", "POST", "/api/formats/movienight/howto", json={"fromEventId": source}
        ),
        201,
    )


async def clone(api: Api, user: str, source: str, **body: Any) -> Any:
    payload = {"startsAt": future(40).isoformat(), **body}
    return await api.request(user, "POST", f"/api/events/{source}/clone", json=payload)


async def documents_of(api: Api, user: str, eid: str) -> dict[str, dict]:
    rows = await ok(await api.request(user, "GET", f"/api/events/{eid}/documents"))
    return {d["kind"]: d for d in rows}


async def test_clone_movienight_own(api: Api) -> None:
    source = await archived_movienight(api)
    await master_howto(api, source)
    start = future(40)
    preview = await ok(
        await api.request("organizer-fsi", "GET", f"/api/events/{source}/clone-preview")
    )
    response = await clone(api, "organizer-fsi", source, startsAt=start.isoformat())
    assert response.status_code == 201, response.text
    assert response.headers["location"].endswith(response.json()["event"]["id"])
    out = response.json()
    event, report = out["event"], out["report"]
    assert report == preview["report"]
    assert event["state"] == "idea" and event["derivedFromId"] == source
    assert event["poster"] is None and event["imageException"] is None
    assert event["title"] == "Movienight: Whiplash" and event["slug"] is None
    assert event["format"]["slug"] == "movienight" and event["outcome"] is None
    assert event["locationPrecision"] == "hidden" and event["venueText"] == "Kinosaal 9-133"
    assert event["costText"] == "Eintritt frei" and event["publishAt"] is None
    eid = event["id"]
    assert (await ok(await api.request("organizer-fsi", "GET", f"/api/events/{eid}/quotes")))[
        "groups"
    ] == []
    assert (
        await ok(await api.request("organizer-fsi", "GET", f"/api/events/{eid}/attachments")) == []
    )
    assert await ok(await api.request("organizer-fsi", "GET", f"/api/events/{eid}/comments")) == []
    checklist = await ok(await api.request("organizer-fsi", "GET", f"/api/events/{eid}/checklist"))
    items = checklist["items"]
    assert items and event["checklistRecomputed"] == len([i for i in items if i["dueAt"]])
    assert all(
        i["doneAt"] is None and i["assigneeSub"] is None and not i["dueManual"] for i in items
    )
    by_text = {i["text"]: i for i in items}
    room = by_text["Raum bestätigt"]
    assert (
        room["dueAt"]
        == (start - timedelta(days=35)).replace(hour=8).isoformat().replace("+00:00", "Z")
        or room["dueOffsetDays"] == -35
    )
    assert by_text["Plakat bestellen"]["dueOffsetDays"] == -28
    assert by_text["Abrechnung"]["dueOffsetDays"] == 7
    docs = await documents_of(api, "organizer-fsi", eid)
    assert set(docs) == {"notes", "mail_template"}
    assert docs["notes"]["rev"] == 1 and docs["notes"]["verifiedAt"] is None
    assert docs["notes"]["visibility"] == "org"
    revision = await ok(
        await api.request("organizer-fsi", "GET", f"/api/documents/{docs['notes']['id']}/revisions")
    )
    assert len(revision) == 1 and revision[0]["changeNote"].startswith("Aus Vorlage")
    howto_line = next(line for line in report if line["part"] == "howto")
    assert howto_line["mode"] == "link"
    last = await ok(await api.request("organizer-fsi", "GET", f"/api/events/{eid}/last-time"))
    assert last["attendance"] == 87 and last["costsCents"] == 24500 and last["restricted"] is False
    assert last["revenueCents"] == 13000 and last["retrospective"]["bodyMd"] == "Der Saal war voll."
    quotes = await api.request("organizer-fsi", "GET", f"/api/events/{source}/quotes")
    assert quotes.status_code == 200 and len(quotes.json()["groups"]) == 2
    events = await api.sql(
        "SELECT revision FROM (SELECT count(*) AS revision FROM event_revision WHERE event_id = :e) t",
        e=eid,
    )
    assert events == [(1,)]


async def test_clone_movienight_foreign(api: Api) -> None:
    source = await archived_movienight(api)
    await master_howto(api, source)
    response = await clone(api, "organizer-makers", source)
    assert response.status_code == 201, response.text
    event = response.json()["event"]
    assert event["organization"]["slug"] == "makers"
    docs = await documents_of(api, "organizer-makers", event["id"])
    assert set(docs) == {"mail_template"}
    checklist = await ok(
        await api.request("organizer-makers", "GET", f"/api/events/{event['id']}/checklist")
    )
    assert checklist["items"] and all(i["fromTemplate"] for i in checklist["items"])
    last = await ok(
        await api.request("organizer-makers", "GET", f"/api/events/{event['id']}/last-time")
    )
    assert last["attendance"] == 87 and last["restricted"] is True
    assert last["costsCents"] is None and last["revenueCents"] is None and last["notes"] is None
    assert last["retrospective"] is None
    for path in ("quotes",):
        hidden = await api.request("organizer-makers", "GET", f"/api/events/{source}/{path}")
        assert hidden.status_code == 404
    assert (
        await api.request("organizer-makers", "GET", f"/api/events/{source}")
    ).status_code == 404
    live = await api.to_state("live", title="Movienight: Live")
    refused = await clone(api, "organizer-makers", live["id"])
    assert refused.status_code == 404


async def test_a_shared_retrospective_is_visible_to_other_organizations(api: Api) -> None:
    source = await archived_movienight(api)
    await api.sql("UPDATE document SET visibility = 'shared' WHERE kind = 'retrospective'")
    event = (await clone(api, "organizer-makers", source)).json()["event"]
    last = await ok(
        await api.request("organizer-makers", "GET", f"/api/events/{event['id']}/last-time")
    )
    assert last["retrospective"]["bodyMd"] == "Der Saal war voll."


async def test_preview_changes_nothing_and_matches_the_report(api: Api) -> None:
    source = await archived_movienight(api)
    before = await api.sql("SELECT count(*) FROM event")
    preview = await ok(
        await api.request("organizer-makers", "GET", f"/api/events/{source}/clone-preview")
    )
    assert await api.sql("SELECT count(*) FROM event") == before
    assert preview["lastTime"]["restricted"] is True and preview["lastTime"]["attendance"] == 87
    made = (await clone(api, "organizer-makers", source)).json()
    assert made["report"] == preview["report"]
    assert {line["part"] for line in preview["report"]} >= {"poster", "files", "history"}
    missing = await api.request("member", "GET", f"/api/events/{source}/clone-preview")
    assert missing.status_code == 403


async def test_clone_is_atomic(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.archive import clone as cloning

    source = await archived_movienight(api)
    before = (await api.sql("SELECT count(*) FROM event"))[0][0]
    docs_before = (await api.sql("SELECT count(*) FROM document"))[0][0]

    def boom(*args: Any, **kwargs: Any) -> int:
        raise RuntimeError("checklist copy failed")

    monkeypatch.setattr(cloning, "_copy_checklist", boom)
    with pytest.raises(RuntimeError):
        await clone(api, "organizer-fsi", source)
    assert (await api.sql("SELECT count(*) FROM event"))[0][0] == before
    assert (await api.sql("SELECT count(*) FROM document"))[0][0] == docs_before


async def test_clone_never_copies_files(api: Api) -> None:
    source = await archived_movienight(api)
    stored = set(api.private.blobs) if hasattr(api.private, "blobs") else set()
    made = (await clone(api, "organizer-fsi", source)).json()["event"]
    assert made["poster"] is None
    assert (await api.sql("SELECT count(*) FROM attachment WHERE event_id = :e", e=made["id"]))[0][
        0
    ] == 0
    assert (set(api.private.blobs) if hasattr(api.private, "blobs") else set()) == stored


async def test_not_a_template_and_organization_rules(api: Api) -> None:
    source = await archived_movienight(api)
    idea = await api.create_event(title="Nur eine Idee")
    refused = await clone(api, "organizer-fsi", idea["id"])
    assert refused.status_code == 409 and refused.json()["code"] == "not_a_template"
    other = await clone(api, "organizer-fsi", source, organizationId=api.org_ids["makers"])
    assert other.status_code == 404
    unknown = await clone(
        api, "organizer-fsi", source, organizationId="00000000-0000-0000-0000-000000000000"
    )
    assert unknown.status_code == 404
    await api.add_user(
        "double",
        {
            "events-double-fsi": ("organizer", "fsi"),
            "events-double-makers": ("organizer", "makers"),
        },
    )
    one_of_two = await clone(api, "double", source)
    assert (
        one_of_two.status_code == 201
        and one_of_two.json()["event"]["organization"]["slug"] == "fsi"
    )
    await api.add_user(
        "triple",
        {
            "events-triple-tec": ("organizer", "tec"),
            "events-triple-makers": ("organizer", "makers"),
        },
    )
    ambiguous = await clone(api, "triple", source)
    assert ambiguous.status_code == 422 and ambiguous.json()["code"] == "organization_required"
    viewer = await clone(api, "viewer-fsi", source)
    assert viewer.status_code == 403


async def test_clone_titles_and_dates(api: Api) -> None:
    source = await archived_movienight(api, title="Movienight WS26/27")
    plain = (await clone(api, "organizer-fsi", source)).json()["event"]
    assert plain["title"] == "Movienight"
    named = (await clone(api, "organizer-fsi", source, title="Besonderer Abend")).json()["event"]
    assert named["title"] == "Besonderer Abend"
    original = await api.get("editor", source)
    start = future(60)
    default_end = (await clone(api, "organizer-fsi", source, startsAt=start.isoformat())).json()[
        "event"
    ]
    from datetime import datetime

    duration = datetime.fromisoformat(original["endsAt"]) - datetime.fromisoformat(
        original["startsAt"]
    )
    assert datetime.fromisoformat(default_end["endsAt"]) - start == duration
    explicit = await clone(
        api,
        "organizer-fsi",
        source,
        startsAt=start.isoformat(),
        endsAt=(start + timedelta(hours=1)).isoformat(),
    )
    assert explicit.status_code == 201 and explicit.json()["event"]["endEstimated"] is False
    backwards = await clone(
        api,
        "organizer-fsi",
        source,
        startsAt=start.isoformat(),
        endsAt=(start - timedelta(hours=1)).isoformat(),
    )
    assert backwards.status_code == 422


async def test_an_all_day_template_keeps_its_number_of_days(api: Api) -> None:
    source = await archived_movienight(api)
    await api.sql(
        "UPDATE event SET all_day = true, starts_on = date '2026-03-27', ends_on = date '2026-03-29' "
        "WHERE id = :e",
        e=source,
    )
    made = (await clone(api, "organizer-fsi", source, startsAt="2026-10-24T22:30:00Z")).json()[
        "event"
    ]
    assert made["allDay"] and made["startsOn"] == "2026-10-25" and made["endsOn"] == "2026-10-27"
    assert made["startsAt"] == "2026-10-24T22:00:00Z" and made["endsAt"] == "2026-10-27T23:00:00Z"


async def test_free_checklist_items_and_hand_set_dates_of_an_own_template(api: Api) -> None:
    source = await archived_movienight(api)
    await api.sql(
        "INSERT INTO checklist_item (event_id, position, text, phase, due_at, due_manual, "
        "assignee_sub, done_at, done_by) SELECT e.id, 'z', 'Freier Punkt', 'live', "
        "e.starts_at - interval '9 days', true, 'sub-org-fsi', now(), 'x' FROM event e WHERE e.id = :e",
        e=source,
    )
    far = await api.sql(
        "INSERT INTO checklist_item (event_id, position, text, phase, due_at, due_manual) "
        "SELECT e.id, 'zz', 'Sehr früh', 'live', e.starts_at - interval '900 days', true "
        "FROM event e WHERE e.id = :e RETURNING 1",
        e=source,
    )
    assert far
    own = (await clone(api, "organizer-fsi", source)).json()["event"]
    items = (
        await api.request("organizer-fsi", "GET", f"/api/events/{own['id']}/checklist")
    ).json()["items"]
    free = next(i for i in items if i["text"] == "Freier Punkt")
    assert free["dueOffsetDays"] == -9 and free["doneAt"] is None and free["fromTemplate"] is False
    early = next(i for i in items if i["text"] == "Sehr früh")
    assert early["dueOffsetDays"] == -365
    foreign = (await clone(api, "organizer-makers", source)).json()["event"]
    theirs = (
        await api.request("organizer-makers", "GET", f"/api/events/{foreign['id']}/checklist")
    ).json()["items"]
    assert "Freier Punkt" not in {i["text"] for i in theirs}


async def test_a_foreign_clone_keeps_no_image_of_the_other_organization(api: Api) -> None:
    source = await archived_movienight(api)
    image = "5b0f8f0e-3f5b-4c1e-9d63-0a1f2b3c4d5e"
    await api.sql(
        "INSERT INTO markdown_image (id, storage_key, mime, size, width, height, created_at) "
        "VALUES (:id, 'k', 'image/png', 1, 1, 1, now())",
        id=image,
    )
    await api.sql(
        "UPDATE event SET description_md = :d WHERE id = :e",
        d=f"Davor ![Saal](/api/media/images/{image}) danach",
        e=source,
    )
    event = (await clone(api, "organizer-makers", source)).json()["event"]
    refs = await api.sql("SELECT 1 FROM media_ref WHERE owner_id = :e", e=event["id"])
    assert refs == [] and "/api/media/images/" not in (event["descriptionMd"] or "")
    own = (await clone(api, "organizer-fsi", source)).json()["event"]
    assert f"/api/media/images/{image}" in own["descriptionMd"]
