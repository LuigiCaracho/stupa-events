"""`GET /tasks`: the lists per role, the Four-Eyes hint and the counts."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future
from tests.integration.pipeline.test_four_eyes import stupa_in_review

pytestmark = pytest.mark.integration


async def tasks(api: Api, user: str) -> dict:
    response = await api.request(user, "GET", "/api/tasks")
    assert response.status_code == 200, response.text
    return response.json()


def ids(cards: list[dict]) -> set[str]:
    return {c["id"] for c in cards}


async def test_awaiting_review_marks_the_own_submission(api: Api) -> None:
    mine = await stupa_in_review(api)
    theirs = (await api.to_state("in_review"))["id"]
    own = await tasks(api, "approver-stupa")
    assert ids(own["awaitingReview"]) == {mine}
    assert own["awaitingReview"][0]["fourEyesBlocked"] is True
    other = await tasks(api, "approver2-stupa")
    assert other["awaitingReview"][0]["fourEyesBlocked"] is False
    editor = await tasks(api, "editor")
    assert ids(editor["awaitingReview"]) == {mine, theirs}
    assert {c["fourEyesBlocked"] for c in editor["awaitingReview"]} == {False}
    assert editor["counts"]["awaitingReview"] == 2
    assert (await tasks(api, "organizer-fsi"))["awaitingReview"] == []
    assert (await tasks(api, "approver-fsi"))["awaitingReview"] == []


async def test_returned_dossiers_carry_the_note(api: Api) -> None:
    event = await api.to_state("in_review")
    await api.add_open_comment(event["id"])
    await api.fire("editor", event["id"], "T03", note="Bitte den Ort nennen")
    organizer = await tasks(api, "organizer-fsi")
    assert ids(organizer["returned"]) == {event["id"]}
    card = organizer["returned"][0]
    assert card["note"] == "Bitte den Ort nennen" and card["returnedBy"]["sub"] == "sub-editor"
    assert card["returnedAt"]
    assert (await tasks(api, "viewer-fsi"))["returned"] == []
    await api.fire("organizer-fsi", event["id"], "T02")
    assert (await tasks(api, "organizer-fsi"))["returned"] == []


async def test_mine_follows_the_organizations_and_the_authorship(api: Api) -> None:
    own = await api.create_event()
    colleague = await api.create_event(user="submitter-fsi", title="Von der Kollegin")
    foreign = await api.create_event(user="organizer-makers", org="makers", title="Makers")
    proposal = (
        await api.request(
            "member",
            "POST",
            "/api/events",
            json={"title": "Idee", "startsAt": future().isoformat()},
        )
    ).json()
    organizer = await tasks(api, "organizer-fsi")
    assert ids(organizer["mine"]) == {own["id"], colleague["id"]}
    assert organizer["counts"]["mine"] == 2
    assert ids((await tasks(api, "organizer-makers"))["mine"]) == {foreign["id"]}
    assert ids((await tasks(api, "member"))["mine"]) == {proposal["id"]}
    assert (await tasks(api, "editor"))["mine"] == []


async def test_followup_open_and_due(api: Api) -> None:
    event = await api.to_state("live")
    await api.sql("UPDATE event SET state = 'followup' WHERE id = :i", i=event["id"])
    organizer = await tasks(api, "organizer-fsi")
    assert ids(organizer["followupOpen"]) == {event["id"]} and organizer["due"] == []
    assert (await tasks(api, "viewer-fsi"))["followupOpen"] == []
    assert organizer["counts"]["due"] == 0


async def test_lists_hold_at_most_fifty_and_counts_the_rest(api: Api) -> None:
    for n in range(52):
        await api.sql(
            "INSERT INTO event (title, starts_at, ends_at, organization_id, created_by) "
            "SELECT :t, now() + interval '3 days', now() + interval '4 days', id, 'sub-org-fsi' "
            "FROM organization WHERE slug = 'fsi'",
            t=f"E{n}",
        )
    organizer = await tasks(api, "organizer-fsi")
    assert len(organizer["mine"]) == 50 and organizer["counts"]["mine"] == 52


async def test_tasks_need_a_session(api: Api) -> None:
    assert (await api.request(None, "GET", "/api/tasks")).status_code == 401
