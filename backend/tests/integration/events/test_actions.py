"""cancel, postpone, reinstate, the organization by PATCH, revert-revision and `allowedActions`."""

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
    event = await api.to_state("published")
    eid = event["id"]
    before = await seq(api, eid)
    done = await api.act(
        "organizer-fsi", eid, "cancel", reason="Referent krank", publicReasonCode="illness"
    )
    assert done.status_code == 200
    body = done.json()
    assert body["state"] == "published" and body["publicStatus"] == "cancelled"
    assert body["publicReason"] == {"code": "illness", "text": None}
    assert await seq(api, eid) == before + 1
    item = await feed_item(api, eid)
    assert item is not None and item["status"] == "cancelled"
    assert item["statusReason"] == {"code": "illness", "text": None}
    assert "Referent krank" not in str(item)


async def test_the_reason_is_internal_only(api: Api) -> None:
    event = await api.to_state("published")
    await api.act("organizer-fsi", event["id"], "cancel", reason="Geheimer Grund")
    status = await api.sql(
        "SELECT note, transition_id, actor_type FROM event_status_event "
        "WHERE event_id = :i ORDER BY id DESC LIMIT 1",
        i=event["id"],
    )
    assert status == [("Geheimer Grund", "cancel", "human")]
    audit = await api.sql("SELECT data::text FROM audit_entry WHERE action = 'event_cancel'")
    assert "Geheimer Grund" not in audit[0][0]
    revisions = await api.sql(
        "SELECT change_note FROM event_revision WHERE change_note IS NOT NULL"
    )
    assert all("Geheimer" not in (r[0] or "") for r in revisions)


async def test_the_organizer_sets_the_public_text_and_the_reason_is_optional(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    done = await api.act(
        "organizer-fsi",
        eid,
        "cancel",
        publicReasonCode="room",
        publicReasonText="Der Saal ist belegt",
    )
    assert done.status_code == 200 and done.json()["publicReason"]["text"] == "Der Saal ist belegt"
    item = await feed_item(api, eid)
    assert item is not None and item["statusReason"]["text"] == "Der Saal ist belegt"


async def test_the_actions_need_the_published_state_and_a_fitting_status(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    assert (await api.act("organizer-fsi", eid, "cancel")).status_code == 200
    again = await api.act("organizer-fsi", eid, "cancel")
    assert again.status_code == 409 and again.json()["code"] == "invalid_state"
    draft = await api.to_state("draft")
    early = await api.act("editor", draft["id"], "cancel")
    assert early.status_code == 409 and early.json()["code"] == "invalid_state"
    archived = await api.to_state("archived")
    late = await api.act("editor", archived["id"], "reinstate")
    assert late.status_code == 409
    bad = await api.act("editor", eid, "postpone", publicReasonCode="nonsense")
    assert bad.status_code == 422


async def test_rights_of_the_status_actions(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    assert (await api.act("viewer-fsi", eid, "cancel")).status_code == 403
    assert (await api.act("submitter-fsi", eid, "cancel")).status_code == 403
    assert (await api.act("organizer-makers", eid, "cancel")).status_code == 404
    assert (await api.act("member", eid, "cancel")).status_code == 403
    assert (await api.act("stupa", eid, "cancel")).status_code == 403
    await api.act("organizer-fsi", eid, "cancel")
    assert (await api.act("organizer-fsi", eid, "reinstate")).status_code == 200
    assert (await api.act("organizer-fsi", eid, "cancel", without_if_match=True)).status_code == 428


async def test_postpone_with_a_new_date_stays_postponed_until_reinstated(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    new_start, new_end = future(30), future(30, 2)
    done = await api.act(
        "organizer-fsi",
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
    back = await api.act("organizer-fsi", eid, "reinstate", reason="Termin steht")
    assert back.status_code == 200 and back.json()["publicStatus"] == "scheduled"
    assert back.json()["publicReason"] is None
    final = await feed_item(api, eid)
    assert final is not None and final["status"] == "scheduled" and final["statusReason"] is None


async def test_postpone_without_a_date_and_its_validation(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    lone = await api.act("editor", eid, "postpone", newEndsAt=future(9).isoformat())
    assert lone.status_code == 422
    past = await api.act("editor", eid, "postpone", newStartsAt=future(-9).isoformat())
    assert past.status_code == 422 and past.json()["code"] == "start_in_past"
    reversed_ = await api.act(
        "editor",
        eid,
        "postpone",
        newStartsAt=future(9).isoformat(),
        newEndsAt=future(8).isoformat(),
    )
    assert reversed_.status_code == 422
    plain = await api.act("organizer-fsi", eid, "postpone", reason="Folgt")
    assert plain.status_code == 200 and plain.json()["startsAt"] == event["startsAt"]
    twice = await api.act("organizer-fsi", eid, "postpone", reason="Folgt")
    assert twice.status_code == 409
    cancelled = await api.act("editor", eid, "cancel", reason="Doch nicht")
    assert cancelled.json()["publicStatus"] == "cancelled"


async def test_postponing_an_all_day_event_moves_its_days(api: Api) -> None:
    event = await api.create_event(
        startsAt=None, endsAt=None, allDay=True, startsOn="2030-05-01", endsOn="2030-05-02"
    )
    assert (await api.act("organizer-fsi", event["id"], "publish")).status_code == 200
    moved = await api.act(
        "organizer-fsi",
        event["id"],
        "postpone",
        newStartsAt="2030-06-09T22:00:00+00:00",
        newEndsAt="2030-06-11T22:00:00+00:00",
    )
    body = moved.json()
    assert moved.status_code == 200
    assert (body["startsOn"], body["endsOn"]) == ("2030-06-10", "2030-06-11")


async def test_assign_the_organization_by_patch(api: Api) -> None:
    await api.sql(
        "INSERT INTO event (title, starts_at, ends_at, created_by, state) "
        "VALUES ('Alter Vorschlag', now() + interval '3 days', now() + interval '4 days', "
        "'sub-member', 'draft')"
    )
    orphan = (await api.sql("SELECT id::text FROM event"))[0][0]
    org = api.org_ids["fsi"]
    assert (await api.get("editor", orphan))["organization"] is None
    assert (await api.patch("organizer-fsi", orphan, organizationId=org)).status_code == 404
    assert (await api.patch("member", orphan, organizationId=org)).status_code == 403
    unknown = await api.patch(
        "editor", orphan, organizationId="00000000-0000-0000-0000-000000000000"
    )
    assert unknown.status_code == 404
    done = await api.patch("editor", orphan, organizationId=org)
    assert done.status_code == 200 and done.json()["organization"]["slug"] == "fsi"
    twice = await api.patch("editor", orphan, organizationId=api.org_ids["makers"])
    assert twice.status_code == 409 and twice.json()["code"] == "field_locked"
    assert (await api.act("organizer-fsi", orphan, "publish")).status_code == 200


async def test_an_orphan_draft_cannot_be_published(api: Api) -> None:
    await api.sql(
        "INSERT INTO event (title, starts_at, ends_at, created_by, state) "
        "VALUES ('Alter Vorschlag', now() + interval '3 days', now() + interval '4 days', "
        "'sub-editor', 'draft')"
    )
    orphan = (await api.sql("SELECT id::text FROM event"))[0][0]
    refused = await api.act("editor", orphan, "publish")
    assert refused.status_code == 422 and refused.json()["code"] == "publish_incomplete"
    assert [e["field"] for e in refused.json()["errors"]] == ["organizationId"]
    assert refused.json()["reasons"] == [{"field": "organizationId"}]


async def test_revert_revision_restores_the_content(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    first_rev = event["rev"]
    await api.patch("organizer-fsi", eid, summary="Vertippt!!", descriptionMd="Neuer Text")
    reverted = await api.act("organizer-fsi", eid, "revert-revision", rev=first_rev)
    assert reverted.status_code == 200
    body = reverted.json()
    assert body["summary"] == event["summary"] and body["descriptionMd"] == event["descriptionMd"]
    assert body["rev"] == first_rev + 2 and body["state"] == "published"
    rows = await api.sql(
        "SELECT change_note FROM event_revision WHERE event_id = :i ORDER BY rev DESC LIMIT 1",
        i=eid,
    )
    assert rows == [(f"Zurückgesetzt auf Revision {first_rev}",)]
    assert (await api.act("editor", eid, "revert-revision", rev=999)).status_code == 404
    assert (await api.act("viewer-fsi", eid, "revert-revision", rev=first_rev)).status_code == 403


async def test_revert_is_refused_when_the_poster_was_replaced(api: Api) -> None:
    event = await api.to_state("draft")
    eid = event["id"]
    first = await api.upload_poster("organizer-fsi", eid)
    await api.process_poster(first.json()["id"])
    rev_with_poster = (await api.get("editor", eid))["rev"]
    second = await api.upload_poster("organizer-fsi", eid, altText="Anderes Bild")
    assert second.status_code == 201
    refused = await api.act("editor", eid, "revert-revision", rev=rev_with_poster)
    assert refused.status_code == 409 and refused.json()["code"] == "revert_poster_replaced"


async def test_revert_is_closed_in_the_archive(api: Api) -> None:
    event = await api.to_state("archived")
    closed = await api.act("editor", event["id"], "revert-revision", rev=1)
    assert closed.status_code == 409 and closed.json()["code"] == "field_locked"


async def test_revert_runs_through_the_same_derivations_as_patch(api: Api) -> None:
    event = await api.to_state("published", venueText="Kinosaal")
    eid = event["id"]
    await api.act("editor", eid, "confirm-location", precision="exact")
    assert (await api.get("editor", eid))["locationPrecision"] == "exact"
    changed = await api.patch("organizer-fsi", eid, venueText="Aula")
    assert changed.status_code == 200 and changed.json()["locationPrecision"] == "hidden"
    await api.act("editor", eid, "confirm-location", precision="building")
    back = await api.act("organizer-fsi", eid, "revert-revision", rev=event["rev"] + 1)
    assert back.status_code == 200 and back.json()["venueText"] == "Kinosaal"
    assert back.json()["locationPrecision"] == "hidden"
    item = await feed_item(api, eid)
    assert item is not None and not item.get("venueText") and "Kinosaal" not in str(item)


async def test_revert_bumps_the_public_sequence_only_for_public_fields(api: Api) -> None:
    published = await api.to_state("published")
    await api.patch("organizer-fsi", published["id"], descriptionMd="Mehr Text")
    before = await seq(api, published["id"])
    done = await api.act("editor", published["id"], "revert-revision", rev=published["rev"])
    assert done.status_code == 200
    assert await seq(api, published["id"]) == before
    await api.patch("organizer-fsi", published["id"], summary="Anders")
    before = await seq(api, published["id"])
    await api.act("editor", published["id"], "revert-revision", rev=published["rev"])
    assert await seq(api, published["id"]) == before + 1


async def test_allowed_actions_in_event_out(api: Api) -> None:
    event = await api.to_state("published")
    editor = await api.get("editor", event["id"])
    assert editor["allowedActions"] == [
        "unpublish",
        "archive",
        "cancel",
        "postpone",
        "revert-revision",
        "confirm-location",
        "verify-howto",
        "save-as-format",
        "clone",
    ]
    organizer = await api.get("organizer-fsi", event["id"])
    assert organizer["allowedActions"] == editor["allowedActions"]
    viewer = await api.get("viewer-fsi", event["id"])
    assert viewer["allowedActions"] == [] and viewer["editableFields"] == []
    assert "title" in editor["editableFields"]


async def test_a_stale_if_match_on_an_action_is_a_conflict(api: Api) -> None:
    event = await api.to_state("published")
    stale = await api.act("organizer-fsi", event["id"], "cancel", if_match_rev=event["rev"] - 1)
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    assert stale.json()["current"]["rev"] == event["rev"]
