"""`GET /events?view=board|list`: columns, moves, blockers, filters and sort."""

from __future__ import annotations

import pytest

from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


def column(board: dict, key: str) -> dict:
    return next(c for c in board["columns"] if c["key"] == key)


async def get_board(api: Api, user: str, query: str = "") -> dict:
    response = await api.request(user, "GET", f"/api/events?view=board{query}")
    assert response.status_code == 200, response.text
    return response.json()


async def test_the_board_has_five_active_columns_with_totals(api: Api) -> None:
    idea = await api.to_state("idea", title="Idee A")
    planning = await api.to_state("planning", title="Plan B")
    review = await api.to_state("in_review", title="Frei C")
    approved = await api.to_state("approved", title="Frei D")
    live = await api.to_state("live", title="Live E")
    board = await get_board(api, "editor")
    assert [c["key"] for c in board["columns"]] == [
        "idea",
        "planning",
        "in_review",
        "published",
        "followup",
    ]
    assert [c["total"] for c in board["columns"]] == [1, 1, 1, 2, 0]
    published = {c["id"] for c in column(board, "published")["items"]}
    assert published == {approved["id"], live["id"]}
    assert column(board, "idea")["items"][0]["id"] == idea["id"]
    assert planning["id"] in {c["id"] for c in column(board, "planning")["items"]}
    assert review["id"] in {c["id"] for c in column(board, "in_review")["items"]}
    assert board["generatedAt"]


async def test_cards_carry_moves_blockers_and_the_next_transition(api: Api) -> None:
    await api.to_state("idea", title="Idee")
    planning = await api.create_event(title="Ohne Ort", venueText=None)
    await api.fire("organizer-fsi", planning["id"], "T01")
    review = await api.to_state("in_review", title="Zur Freigabe")
    board = await get_board(api, "editor")
    idea_card = column(board, "idea")["items"][0]
    assert idea_card["moves"] == {"planning": "T01"} and idea_card["nextTransition"] == "T01"
    assert idea_card["blockers"] == [] and idea_card["blockerCount"] == 0
    assert idea_card["hasPoster"] is False and idea_card["openQuestions"] == 0
    assert idea_card["createdBy"]["sub"] == "sub-org-fsi"
    assert "descriptionMd" not in idea_card
    plan_card = column(board, "planning")["items"][0]
    assert plan_card["nextTransition"] == "T02" and plan_card["blockerCount"] == 1
    assert plan_card["blockers"][0]["code"] == "venue_missing"
    review_card = next(c for c in column(board, "in_review")["items"] if c["id"] == review["id"])
    assert review_card["moves"] == {"planning": "T03", "published": "T04"}
    approved = await api.to_state("approved", title="Freigegeben")
    approved_card = next(
        c
        for c in column(await get_board(api, "editor"), "published")["items"]
        if c["id"] == approved["id"]
    )
    assert (
        approved_card["moves"] == {"in_review": "T06"} and approved_card["nextTransition"] == "T05"
    )


async def test_blockers_are_shown_only_when_the_move_is_allowed(api: Api) -> None:
    planning = await api.create_event(venueText=None)
    await api.fire("organizer-fsi", planning["id"], "T01")
    viewer = await get_board(api, "viewer-fsi")
    card = column(viewer, "planning")["items"][0]
    assert card["nextTransition"] is None and card["blockers"] == [] and card["moves"] == {}


async def test_blockers_are_cut_to_three(api: Api) -> None:
    event = await api.create_event(venueText=None, summary=None, primaryCategoryId=None)
    await api.fire("organizer-fsi", event["id"], "T01")
    await api.sql("UPDATE event SET end_estimated = true WHERE id = :i", i=event["id"])
    card = column(await get_board(api, "organizer-fsi"), "planning")["items"][0]
    assert len(card["blockers"]) == 3 and card["blockerCount"] == 3


async def test_archive_and_withdrawn_are_single_column_views(api: Api) -> None:
    gone = await api.create_event(title="Weg")
    await api.fire("organizer-fsi", gone["id"], "T11", note="x")
    for state in ("archived", "withdrawn"):
        board = await get_board(api, "editor", f"&state={state}")
        assert [c["key"] for c in board["columns"]] == [state]
    withdrawn = await get_board(api, "editor", "&state=withdrawn")
    assert withdrawn["columns"][0]["total"] == 1
    active = await get_board(api, "editor")
    assert sum(c["total"] for c in active["columns"]) == 0


async def test_state_filter_on_the_board_and_truncation(api: Api) -> None:
    for n in range(3):
        await api.create_event(title=f"Idee {n}")
    await api.to_state("planning", title="Plan")
    board = await get_board(api, "editor", "&columnLimit=2&state=idea")
    idea = column(board, "idea")
    assert idea["total"] == 3 and len(idea["items"]) == 2 and idea["truncated"] is True
    assert column(board, "planning")["total"] == 0
    bad = await api.request("editor", "GET", "/api/events?view=board&columnLimit=0")
    assert bad.status_code == 422


async def test_columns_sort_ascending_and_followup_descending(api: Api) -> None:
    late = await api.create_event(
        title="Spät", startsAt=future(30).isoformat(), endsAt=future(30, 2).isoformat()
    )
    early = await api.create_event(
        title="Früh", startsAt=future(5).isoformat(), endsAt=future(5, 2).isoformat()
    )
    ideas = column(await get_board(api, "editor"), "idea")["items"]
    assert [c["id"] for c in ideas] == [early["id"], late["id"]]
    await api.sql("UPDATE event SET state = 'followup'")
    follow = column(await get_board(api, "editor"), "followup")["items"]
    assert [c["id"] for c in follow] == [late["id"], early["id"]]


async def test_list_view_filters(api: Api) -> None:
    kino = await api.create_event(
        title="Kinoabend", primaryCategoryId=api.category_ids["kino"], summary="Film"
    )
    other = await api.create_event(
        user="organizer-makers",
        org="makers",
        title="Löten",
        summary="Lötkolben",
        primaryCategoryId=api.category_ids["workshop"],
    )
    now = (await api.request("editor", "GET", "/api/events")).json()
    assert now["total"] == 2 and "descriptionMd" not in now["items"][0]

    def ids(response: object) -> set[str]:
        return {e["id"] for e in response.json()["items"]}  # type: ignore[attr-defined]

    assert ids(await api.request("editor", "GET", "/api/events?organization=makers")) == {
        other["id"]
    }
    assert ids(await api.request("editor", "GET", "/api/events?category=kino")) == {kino["id"]}
    assert ids(await api.request("editor", "GET", "/api/events?q=film")) == {kino["id"]}
    assert ids(await api.request("organizer-fsi", "GET", "/api/events?mine=1")) == {kino["id"]}
    assert ids(await api.request("editor", "GET", "/api/events?mine=1")) == set()
    assert ids(await api.request("editor", "GET", "/api/events?state=idea&state=planning")) == {
        kino["id"],
        other["id"],
    }
    assert ids(await api.request("editor", "GET", "/api/events?state=live")) == set()


async def test_category_filter_includes_children_and_dates_are_berlin_local(api: Api) -> None:
    parent = await api.sql("SELECT id, slug FROM category WHERE parent_id IS NOT NULL LIMIT 1")
    child_id, _ = parent[0]
    row = await api.sql(
        "SELECT slug FROM category WHERE id = (SELECT parent_id FROM category WHERE id = :c)",
        c=child_id,
    )
    parent_slug = row[0][0]
    event = await api.create_event(primaryCategoryId=str(child_id))
    listed = await api.request("editor", "GET", f"/api/events?category={parent_slug}")
    assert [e["id"] for e in listed.json()["items"]] == [event["id"]]
    await api.sql(
        "UPDATE event SET starts_at = '2031-06-30T22:30:00Z', ends_at = '2031-07-01T00:30:00Z' WHERE id = :i",
        i=event["id"],
    )
    on_july_first = await api.request("editor", "GET", "/api/events?from=2031-07-01&to=2031-07-01")
    assert [e["id"] for e in on_july_first.json()["items"]] == [event["id"]]
    on_june_30 = await api.request("editor", "GET", "/api/events?from=2031-06-30&to=2031-06-30")
    assert on_june_30.json()["items"] == []


async def test_sort_and_paging(api: Api) -> None:
    ids = []
    for n in (3, 1, 2):
        ids.append(
            (
                await api.create_event(
                    title=f"E{n}",
                    startsAt=future(n * 5).isoformat(),
                    endsAt=future(n * 5, 2).isoformat(),
                )
            )["id"]
        )
    asc = (await api.request("editor", "GET", "/api/events")).json()
    desc = (await api.request("editor", "GET", "/api/events?sort=-startsAt")).json()
    assert [e["id"] for e in desc["items"]] == [e["id"] for e in reversed(asc["items"])]
    page = (await api.request("editor", "GET", "/api/events?limit=1&offset=1")).json()
    assert page["total"] == 3 and len(page["items"]) == 1


async def test_a_partner_never_sees_a_foreign_organization_on_the_board(api: Api) -> None:
    await api.create_event(title="Fachschaft")
    own = await api.create_event(user="submitter-ekhg", org="ekhg", title="Partnerfest")
    board = await get_board(api, "submitter-ekhg")
    ids = {c["id"] for col in board["columns"] for c in col["items"]}
    assert ids == {own["id"]}
    listed = (await api.request("submitter-ekhg", "GET", "/api/events")).json()
    assert [e["id"] for e in listed["items"]] == [own["id"]]
