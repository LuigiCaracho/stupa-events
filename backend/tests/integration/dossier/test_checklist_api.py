"""Checklists: templates, due dates after a date change, waivers, assignees; open items never block publishing."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.integration.dossier.helpers import draft_event, seed_principals
from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def apply(api: Api, eid: str, user: str = "organizer-fsi", **body: object):  # noqa: ANN201
    return await api.request(user, "POST", f"/api/events/{eid}/checklist/apply-template", json=body)


async def items(api: Api, eid: str) -> dict[str, dict]:
    data = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/checklist")).json()
    return {i["text"]: i for i in data["items"]}


async def test_the_template_follows_the_category_profile_and_is_idempotent(api: Api) -> None:
    party = await draft_event(api, primaryCategoryId=api.category_ids["party"])
    first = await apply(api, party)
    assert first.status_code == 200 and first.json()["added"] == 9
    assert first.json()["template"]["slug"] == "party"
    second = await apply(api, party)
    assert second.json()["added"] == 0 and len(second.json()["items"]) == 9
    movie = await draft_event(api)
    generic = (await apply(api, movie)).json()
    assert generic["template"]["slug"] == "generic" and generic["added"] == 6
    forced = (await apply(api, movie, templateSlug="meeting")).json()
    assert forced["added"] == 2 and len(forced["items"]) == 8
    assert (await apply(api, movie, templateSlug="nope")).status_code == 404
    assert (await apply(api, movie, user="viewer-fsi")).status_code == 403
    assert (await apply(api, movie, user="organizer-makers")).status_code == 404


async def test_due_dates_follow_a_new_start_but_not_manual_or_finished_items(api: Api) -> None:
    eid = await draft_event(api)
    await apply(api, eid)
    rows = await items(api, eid)
    poster = rows["Plakat bestellen"]
    start = datetime.fromisoformat((await api.get("editor", eid))["startsAt"])
    expected = (start - timedelta(days=28)).astimezone(UTC)
    due = datetime.fromisoformat(poster["dueAt"])
    assert (due.hour, due.minute) in {(7, 0), (8, 0)} and abs((due - expected).days) <= 1
    manual = datetime(2031, 5, 5, 8, 0, tzinfo=UTC)
    held = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/checklist-items/{rows['Technik bestätigen']['id']}",
        json={"dueAt": manual.isoformat()},
    )
    assert held.status_code == 200 and held.json()["dueManual"] is True
    done = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/checklist-items/{rows['Abrechnung']['id']}/done",
        json={"done": True},
    )
    assert done.status_code == 200
    before_done = done.json()["dueAt"]
    moved = future(days=24)
    response = await api.patch(
        "organizer-fsi",
        eid,
        startsAt=moved.isoformat(),
        endsAt=(moved + timedelta(hours=3)).isoformat(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["checklistRecomputed"] == 4
    after = await items(api, eid)
    assert after["Plakat bestellen"]["dueAt"] != poster["dueAt"]
    assert after["Technik bestätigen"]["dueAt"] == manual.isoformat().replace("+00:00", "Z")
    assert after["Abrechnung"]["dueAt"] == before_done and after["Abrechnung"]["doneAt"]


async def test_handing_a_date_back_to_the_rule(api: Api) -> None:
    eid = await draft_event(api)
    await apply(api, eid)
    row = (await items(api, eid))["Raum bestätigt"]
    url = f"/api/checklist-items/{row['id']}"
    manual = datetime(2031, 5, 5, 8, 0, tzinfo=UTC).isoformat()
    await api.request("organizer-fsi", "PATCH", url, json={"dueAt": manual})
    back = await api.request("organizer-fsi", "PATCH", url, json={"dueAt": None})
    assert back.json()["dueManual"] is False and back.json()["dueAt"] == row["dueAt"]


async def test_postpone_with_a_new_date_recomputes_the_due_dates(api: Api) -> None:
    event = await api.to_state("published")
    eid = event["id"]
    await apply(api, eid, user="editor")
    before = (await items(api, eid))["Plakat bestellen"]["dueAt"]
    new = future(days=90)
    postponed = await api.act(
        "editor",
        eid,
        "postpone",
        reason="Terminverschiebung",
        publicReasonCode="room",
        newStartsAt=new.isoformat(),
        newEndsAt=(new + timedelta(hours=3)).isoformat(),
    )
    assert postponed.status_code == 200, postponed.text
    assert postponed.json()["checklistRecomputed"] >= 1
    assert (await items(api, eid))["Plakat bestellen"]["dueAt"] != before


async def test_waivers_assignees_and_the_free_items(api: Api) -> None:
    await seed_principals(api)
    eid = await draft_event(api)
    await apply(api, eid)
    rows = await items(api, eid)
    required, optional = rows["Raum bestätigt"], rows["Plakat bestellen"]
    short = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/checklist-items/{required['id']}",
        json={"waivedReason": "kurz"},
    )
    assert short.status_code == 422 and short.json()["code"] == "waiver_reason_required"
    waived = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/checklist-items/{required['id']}",
        json={"waivedReason": "Raum ist fest gebucht"},
    )
    assert waived.status_code == 200 and waived.json()["waivedReason"]
    blocked = await api.request(
        "organizer-fsi", "POST", f"/api/checklist-items/{required['id']}/done", json={"done": True}
    )
    assert blocked.status_code == 409 and blocked.json()["code"] == "item_waived"
    empty = await api.request(
        "organizer-fsi",
        "PATCH",
        f"/api/checklist-items/{optional['id']}",
        json={"waivedReason": " "},
    )
    assert empty.json()["waivedReason"] is None
    template_edit = await api.request(
        "organizer-fsi", "PATCH", f"/api/checklist-items/{optional['id']}", json={"text": "Anders"}
    )
    assert template_edit.status_code == 409 and template_edit.json()["code"] == "template_item"
    assert (
        await api.request("organizer-fsi", "DELETE", f"/api/checklist-items/{optional['id']}")
    ).status_code == 409
    free = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/checklist/items",
        json={"text": "Kuchen backen", "phase": "live", "assigneeSub": "sub-sub-fsi"},
    )
    assert free.status_code == 201 and free.json()["assigneeName"] == "Submitter Fsi"
    outsider = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/checklist/items",
        json={"text": "Nix", "phase": "live", "assigneeSub": "sub-sub-ekhg"},
    )
    assert outsider.status_code == 422 and outsider.json()["code"] == "assignee_not_member"
    gone = await api.request("organizer-fsi", "DELETE", f"/api/checklist-items/{free.json()['id']}")
    assert gone.status_code == 204


async def test_an_open_required_planning_item_does_not_block_publishing(api: Api) -> None:
    eid = await draft_event(api)
    await apply(api, eid)
    assert "Raum bestätigt" in await items(api, eid)
    assert (await api.act("organizer-fsi", eid, "publish")).status_code == 200


async def test_the_assignee_may_finish_the_item(api: Api) -> None:
    await seed_principals(api)
    eid = await draft_event(api)
    item = (
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{eid}/checklist/items",
            json={"text": "Kuchen", "phase": "live", "assigneeSub": "sub-sub-fsi"},
        )
    ).json()
    other = await api.request(
        "viewer-fsi", "POST", f"/api/checklist-items/{item['id']}/done", json={"done": True}
    )
    assert other.status_code == 403
    done = await api.request(
        "submitter-fsi", "POST", f"/api/checklist-items/{item['id']}/done", json={"done": True}
    )
    assert done.status_code == 200 and done.json()["doneBy"] == "sub-sub-fsi"


async def test_a_new_assignee_gets_no_notification(api: Api) -> None:
    await seed_principals(api)
    eid = await draft_event(api)
    await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/checklist/items",
        json={"text": "Kuchen", "phase": "live", "assigneeSub": "sub-sub-fsi"},
    )
    assert (await api.sql("SELECT count(*) FROM notification"))[0][0] == 0
    await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/checklist/items",
        json={"text": "Selbst", "phase": "live", "assigneeSub": "sub-org-fsi"},
    )
    assert (await api.sql("SELECT count(*) FROM notification"))[0][0] == 0
