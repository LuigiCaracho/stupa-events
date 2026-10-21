"""Reference data of the migration, the organization and category lists, event list scoping."""

from __future__ import annotations

import pytest

from app.modules.taxonomy.reference import CATEGORIES, ORGANIZATIONS
from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


async def test_organization_list(api: Api) -> None:
    everyone = (await api.request("nobody", "GET", "/api/organizations")).json()
    assert {"fsi", "makers", "stupa"} <= {o["slug"] for o in everyone}
    assert set(everyone[0]) == {"id", "slug", "name", "short"}
    mine = (await api.request("organizer-fsi", "GET", "/api/organizations?creatable=true")).json()
    assert [o["slug"] for o in mine] == ["fsi"]
    editor = (await api.request("editor", "GET", "/api/organizations?creatable=true")).json()
    assert len(editor) == len(ORGANIZATIONS)
    assert (await api.request(None, "GET", "/api/organizations")).status_code == 401


async def test_category_list(api: Api) -> None:
    cats = (await api.request("organizer-fsi", "GET", "/api/categories")).json()
    kino = next(c for c in cats if c["slug"] == "kino")
    assert {k: v for k, v in kino.items() if k != "id"} == {
        "slug": "kino",
        "name": "Kino",
        "kind": "format",
        "parentId": None,
        "short": None,
        "colorToken": None,
        "requiredProfile": "generic",
        "sort": 0,
    }
    fsi = next(c for c in cats if c["slug"] == "fachschaft-informatik-fsi")
    assert (fsi["short"], fsi["colorToken"], fsi["kind"]) == ("FSI", "petrol", "fachschaft")
    assert fsi["parentId"] == next(c["id"] for c in cats if c["slug"] == "fachschaft")
    assert len(cats) == len(CATEGORIES)


async def test_event_list_is_scoped_in_sql_sorted_and_paged(api: Api) -> None:
    ids = {}
    for n, (user, org) in enumerate(
        [("organizer-fsi", "fsi"), ("organizer-fsi", "fsi"), ("organizer-makers", "makers")]
    ):
        event = await api.create_event(
            user=user,
            org=org,
            title=f"Titel {n}",
            startsAt=future(5 - n).isoformat(),
            endsAt=future(5 - n, 1).isoformat(),
        )
        ids[n] = event["id"]
    fsi = (await api.request("organizer-fsi", "GET", "/api/events")).json()
    assert [e["id"] for e in fsi["items"]] == [ids[1], ids[0]] and fsi["total"] == 2
    assert (fsi["limit"], fsi["offset"]) == (50, 0)
    everything = (await api.request("editor", "GET", "/api/events")).json()
    assert [e["id"] for e in everything["items"]] == [ids[2], ids[1], ids[0]]
    page = (await api.request("editor", "GET", "/api/events?limit=1&offset=1")).json()
    assert [e["id"] for e in page["items"]] == [ids[1]] and page["total"] == 3
    assert (await api.request("nobody", "GET", "/api/events")).json() == {
        "items": [],
        "total": 0,
        "limit": 50,
        "offset": 0,
    }


async def test_event_list_filters(api: Api) -> None:
    first = await api.create_event(title="Kinoabend 100%")
    await api.create_event(title="Spieleabend", summary="Brettspiele")
    await api.fire("organizer-fsi", first["id"], "T01")

    def titles(response: object) -> list[str]:
        return [e["title"] for e in response.json()["items"]]  # type: ignore[attr-defined]

    assert titles(await api.request("editor", "GET", "/api/events?state=planning")) == [
        "Kinoabend 100%"
    ]
    assert titles(await api.request("editor", "GET", "/api/events?q=brett")) == ["Spieleabend"]
    assert titles(await api.request("editor", "GET", "/api/events?q=100%25")) == ["Kinoabend 100%"]
    assert titles(await api.request("editor", "GET", "/api/events?q=%25")) == ["Kinoabend 100%"]
    assert titles(await api.request("editor", "GET", "/api/events?q=_")) == []
    assert titles(await api.request("editor", "GET", "/api/events?organization=makers")) == []
    assert titles(await api.request("editor", "GET", "/api/events?organization=nope")) == []
    for bad in ("limit=0", "limit=201", "offset=-1", "from=x", "view=cards"):
        assert (await api.request("editor", "GET", f"/api/events?{bad}")).status_code == 422


async def test_create_validation_errors_are_problem_json(api: Api) -> None:
    body = {
        "title": "",
        "startsAt": "2026-11-05T18:00:00",
        "endsAt": "2026-11-05T17:00:00+01:00",
        "organizationId": api.org_ids["fsi"],
        "allDay": True,
        "tzid": "UTC",
    }
    response = await api.request("organizer-fsi", "POST", "/api/events", json=body)
    problem = response.json()
    assert response.status_code == 422 and problem["code"] == "validation_error"
    assert {e["field"].split(".")[-1] for e in problem["errors"]} >= {
        "title",
        "startsAt",
        "tzid",
    }
    unknown_category = await api.request(
        "organizer-fsi",
        "POST",
        "/api/events",
        json={
            **body,
            "title": "x",
            "startsAt": future().isoformat(),
            "endsAt": future(hours=1).isoformat(),
            "allDay": False,
            "tzid": "Europe/Berlin",
            "primaryCategoryId": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert unknown_category.status_code == 422
    missing_org = await api.request(
        "organizer-fsi",
        "POST",
        "/api/events",
        json={
            **body,
            "title": "x",
            "startsAt": future().isoformat(),
            "endsAt": future(hours=1).isoformat(),
            "allDay": False,
            "tzid": "Europe/Berlin",
            "organizationId": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert missing_org.status_code == 404


async def test_patch_validation(api: Api) -> None:
    event = await api.create_event()
    url = f"/api/events/{event['id']}"
    for body in (
        {"rev": 1, "title": None},
        {"rev": 1, "startsAt": None},
        {"rev": 1, "endsAt": "2000-01-01T00:00:00Z"},
        {"rev": 1, "primaryCategoryId": "00000000-0000-0000-0000-000000000000"},
        {"rev": 1, "allDay": True},
        {"rev": 1, "ticketUrl": "http://nicht-sicher.example"},
        {"rev": 1, "websiteUrl": "https://user@example.org"},
        {"rev": 1, "venueId": "00000000-0000-0000-0000-000000000000"},
    ):
        response = await api.request("organizer-fsi", "PATCH", url, json=body)
        assert response.status_code == 422, body
    assert (
        await api.request("organizer-fsi", "PATCH", url, json={"title": "ohne rev"})
    ).status_code == 428
    unchanged = (await api.request("organizer-fsi", "GET", url)).json()
    assert unchanged["rev"] == 1
    set_null = await api.request(
        "organizer-fsi", "PATCH", url, json={"rev": 1, "venueText": None, "primaryCategoryId": None}
    )
    assert set_null.status_code == 200 and set_null.json()["venueText"] is None
    assert set_null.json()["primaryCategory"] is None


async def test_allowed_transitions_follow_state_and_role(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    assert event["allowedTransitions"] == ["T01", "T11"]
    as_editor = (await api.request("editor", "GET", f"/api/events/{eid}")).json()
    assert as_editor["allowedTransitions"] == ["T01", "T11"]
    as_viewer = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}")).json()
    assert as_viewer["allowedTransitions"] == []
    planning = (await api.fire("organizer-fsi", eid, "T01")).json()
    assert planning["allowedTransitions"] == ["T02", "T11"]
