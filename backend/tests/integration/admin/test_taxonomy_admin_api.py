"""The taxonomy admin API: organizations, categories and venues."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from tests.integration.events.harness import Api
from tests.unit.test_route_authz_inventory import _routes

pytestmark = pytest.mark.integration
ORGS, CATS, VENUES = "/api/admin/organizations", "/api/admin/categories", "/api/admin/venues"


def org(slug: str = "neu", **over: object) -> dict[str, object]:
    return {"slug": slug, "name": "Neue Gruppe", "kind": "referat", "short": "NEU", **over}


async def test_organization_create_patch_and_list(api: Api) -> None:
    made = await api.request("editor", "POST", ORGS, json=org(instagram=["@neu.gruppe"]))
    assert made.status_code == 201
    row = made.json()
    assert "trusted" not in row and row["active"] is True and row["instagram"] == ["neu.gruppe"]
    patched = await api.request(
        "editor",
        "PATCH",
        f"{ORGS}/{row['id']}",
        json={"name": "Neuer Name", "colorToken": "navy", "categoryId": api.category_ids["kino"]},
    )
    assert patched.status_code == 200 and patched.json()["colorToken"] == "navy"
    cleared = await api.request("editor", "PATCH", f"{ORGS}/{row['id']}", json={"colorToken": None})
    assert cleared.json()["colorToken"] is None
    hidden = await api.request("editor", "PATCH", f"{ORGS}/{row['id']}", json={"active": False})
    assert hidden.json()["active"] is False
    everyone = (await api.request("editor", "GET", ORGS)).json()
    assert row["id"] in [o["id"] for o in everyone]
    public = (await api.request("editor", "GET", "/api/organizations")).json()
    assert row["id"] not in [o["id"] for o in public]


async def test_blank_names_are_422(api: Api) -> None:
    for body in (org(name="   "), org(short=" "), org(name="\u00a0\t")):
        response = await api.request("editor", "POST", ORGS, json=body)
        assert response.status_code == 422, body


async def test_an_organization_parent_chain_cannot_loop(api: Api) -> None:
    a = (await api.request("editor", "POST", ORGS, json=org("loop-a"))).json()
    b = (await api.request("editor", "POST", ORGS, json=org("loop-b", parentId=a["id"]))).json()
    looped = await api.request("editor", "PATCH", f"{ORGS}/{a['id']}", json={"parentId": b["id"]})
    assert looped.status_code == 422 and looped.json()["code"] == "organization_cycle"
    own = await api.request("editor", "PATCH", f"{ORGS}/{a['id']}", json={"parentId": a["id"]})
    assert own.json()["code"] == "organization_cycle"


async def test_slug_rules(api: Api) -> None:
    await api.request("editor", "POST", ORGS, json=org())
    taken = await api.request("editor", "POST", ORGS, json=org())
    assert taken.status_code == 409 and taken.json()["code"] == "slug_taken"
    for bad in ("Neu", "-neu", "n eu", "x" * 61, ""):
        assert (await api.request("editor", "POST", ORGS, json=org(bad))).status_code == 422
    made = (await api.request("editor", "POST", ORGS, json=org("slug-fest"))).json()
    changed = await api.request("editor", "PATCH", f"{ORGS}/{made['id']}", json={"slug": "anders"})
    assert changed.status_code == 422
    assert changed.json()["code"] == "validation_error"


async def test_unknown_references_and_values_are_422(api: Api) -> None:
    zero = "00000000-0000-0000-0000-000000000000"
    for extra in (
        {"parentId": zero},
        {"categoryId": zero},
        {"colorToken": "#ff0000"},
        {"kind": "x"},
    ):
        assert (await api.request("editor", "POST", ORGS, json=org(**extra))).status_code == 422
    assert (await api.request("editor", "PATCH", f"{ORGS}/{zero}", json={})).status_code == 404
    made = (await api.request("editor", "POST", ORGS, json=org())).json()
    nulled = await api.request("editor", "PATCH", f"{ORGS}/{made['id']}", json={"name": None})
    assert nulled.status_code == 422
    selfparent = await api.request(
        "editor", "PATCH", f"{ORGS}/{made['id']}", json={"parentId": made["id"]}
    )
    assert selfparent.json()["code"] == "organization_cycle"
    badhandle = await api.request("editor", "POST", ORGS, json=org("x1", instagram=["no way"]))
    assert badhandle.status_code == 422


async def test_category_tree_cycle_and_patch(api: Api) -> None:
    root = (
        await api.request(
            "editor", "POST", CATS, json={"slug": "wurzel", "name": "Wurzel", "kind": "format"}
        )
    ).json()
    child = (
        await api.request(
            "editor",
            "POST",
            CATS,
            json={
                "slug": "kind",
                "name": "Kind",
                "kind": "format",
                "parentId": root["id"],
                "sort": 2,
            },
        )
    ).json()
    cycle = await api.request(
        "editor", "PATCH", f"{CATS}/{root['id']}", json={"parentId": child["id"]}
    )
    assert cycle.status_code == 422 and cycle.json()["code"] == "category_cycle"
    own = await api.request(
        "editor", "PATCH", f"{CATS}/{root['id']}", json={"parentId": root["id"]}
    )
    assert own.json()["code"] == "category_cycle"
    unknown = await api.request(
        "editor",
        "PATCH",
        f"{CATS}/{root['id']}",
        json={"parentId": "00000000-0000-0000-0000-000000000000"},
    )
    assert unknown.status_code == 422
    tree = (await api.request("editor", "GET", "/api/categories?tree=true")).json()
    node = next(n for n in tree if n["slug"] == "wurzel")
    assert [c["slug"] for c in node["children"]] == ["kind"] and node["children"][0][
        "children"
    ] == []
    flat = (await api.request("editor", "GET", "/api/categories")).json()
    assert "children" not in flat[0] and {
        "parentId",
        "short",
        "colorToken",
        "requiredProfile",
        "sort",
    } <= set(flat[0])
    hidden = await api.request("editor", "PATCH", f"{CATS}/{child['id']}", json={"active": False})
    assert hidden.json()["active"] is False
    after = (await api.request("editor", "GET", "/api/categories?tree=true")).json()
    assert next(n for n in after if n["slug"] == "wurzel")["children"] == []
    assert (
        await api.request(
            "editor", "POST", CATS, json={"slug": "kino", "name": "x", "kind": "format"}
        )
    ).status_code == 409
    ok = await api.request(
        "editor",
        "PATCH",
        f"{CATS}/{root['id']}",
        json={"colorToken": "red", "short": "W", "requiredProfile": "party"},
    )
    assert ok.json()["colorToken"] == "red" and ok.json()["requiredProfile"] == "party"
    assert (
        await api.request("editor", "PATCH", f"{CATS}/{root['id']}", json={"slug": "neu"})
    ).status_code == 422


async def test_the_tree_root_of_an_inactive_parent_is_the_child(api: Api) -> None:
    fachschaft = next(
        c for c in (await api.request("editor", "GET", CATS)).json() if c["slug"] == "fachschaft"
    )
    await api.request("editor", "PATCH", f"{CATS}/{fachschaft['id']}", json={"active": False})
    tree = (await api.request("editor", "GET", "/api/categories?tree=true")).json()
    assert "fachschaft-informatik-fsi" in [n["slug"] for n in tree]


async def test_venue_create_patch_pin_and_masking(api: Api) -> None:
    made = await api.request(
        "editor",
        "POST",
        VENUES,
        json={
            "slug": "neuer-ort",
            "name": "Neuer Ort",
            "address": "Hauptstraße 1",
            "city": "Reutlingen",
            "roomKey": "Raum 9-U09",
        },
    )
    assert made.status_code == 201
    venue = made.json()
    assert venue["roomKey"] == "9-u9" and venue["publicPrecision"] == "hidden"
    assert venue["lat"] is None and venue["geocodeSource"] is None
    pinned = await api.request(
        "editor", "PATCH", f"{VENUES}/{venue['id']}", json={"lat": 48.49, "lon": 9.2}
    )
    assert pinned.status_code == 200
    body = pinned.json()
    assert (float(body["lat"]), float(body["lon"])) == (48.49, 9.2)
    assert body["geocodeSource"] == "pin" and body["geocodedAt"] is not None
    cleared = await api.request(
        "editor", "PATCH", f"{VENUES}/{venue['id']}", json={"lat": None, "lon": None}
    )
    assert cleared.json()["lat"] is None and cleared.json()["geocodeSource"] is None
    assert cleared.json()["geocodedAt"] is None
    private = await api.request(
        "editor", "PATCH", f"{VENUES}/{venue['id']}", json={"isPrivate": True}
    )
    assert private.status_code == 200
    visible = next(
        v
        for v in (await api.request("member", "GET", "/api/venues")).json()
        if v["slug"] == "neuer-ort"
    )
    assert visible["address"] is None and visible["city"] is None and visible["postcode"] is None
    assert visible["roomKey"] == "9-u9"
    await api.request("editor", "PATCH", f"{VENUES}/{venue['id']}", json={"active": False})
    assert "neuer-ort" not in [
        v["slug"] for v in (await api.request("member", "GET", "/api/venues")).json()
    ]
    assert "neuer-ort" in [v["slug"] for v in (await api.request("editor", "GET", VENUES)).json()]


async def test_venue_coordinate_rules(api: Api) -> None:
    base = {"slug": "koordinaten", "name": "Koordinaten"}
    for extra in ({"lat": 48.1}, {"lon": 9.1}):
        response = await api.request("editor", "POST", VENUES, json={**base, **extra})
        assert response.status_code == 422 and response.json()["code"] == "coordinates_incomplete"
    for extra in ({"lat": 91, "lon": 9}, {"lat": 48, "lon": 181}, {"lat": 48.1234567, "lon": 9}):
        assert (
            await api.request("editor", "POST", VENUES, json={**base, **extra})
        ).status_code == 422
    made = (
        await api.request("editor", "POST", VENUES, json={**base, "lat": 48.1, "lon": 9.1})
    ).json()
    assert made["geocodeSource"] == "pin"
    half = await api.request("editor", "PATCH", f"{VENUES}/{made['id']}", json={"lat": 48.2})
    assert half.json()["code"] == "coordinates_incomplete"
    mixed = await api.request(
        "editor", "PATCH", f"{VENUES}/{made['id']}", json={"lat": 48.2, "lon": None}
    )
    assert mixed.status_code == 422
    assert (
        await api.request(
            "editor", "POST", VENUES, json={**base, "slug": "kino"[:0] or "koordinaten"}
        )
    ).status_code == 409
    assert (
        await api.request("editor", "PATCH", f"{VENUES}/{made['id']}", json={"slug": "x"})
    ).status_code == 422
    assert (
        await api.request(
            "editor", "PATCH", f"{VENUES}/{made['id']}", json={"publicPrecision": "exact"}
        )
    ).json()["publicPrecision"] == "exact"
    zero = "00000000-0000-0000-0000-000000000000"
    assert (await api.request("editor", "PATCH", f"{VENUES}/{zero}", json={})).status_code == 404


async def test_there_is_no_delete_route_for_the_taxonomy() -> None:
    deletes = [path for method, path, _ in _routes() if method == "DELETE"]
    assert sorted(deletes) == [
        "/api/admin/group-mappings/{mapping_id}",
        "/api/checklist-items/{item_id}",
        "/api/documents/{document_id}/draft",
        "/api/events/{event_id}/actions/verify-howto",
        "/api/events/{event_id}/draft",
        "/api/quotes/{quote_id}",
    ]


async def test_delete_on_the_taxonomy_is_405(api: Api) -> None:
    zero = "00000000-0000-0000-0000-000000000000"
    for path in (ORGS, CATS, VENUES):
        assert (await api.request("admin", "DELETE", f"{path}/{zero}")).status_code == 405


async def test_config_changes_audit_field_names_only(api: Api) -> None:
    made = (
        await api.request(
            "editor",
            "POST",
            VENUES,
            json={"slug": "audit-ort", "name": "Audit", "address": "Geheimweg 7"},
        )
    ).json()
    await api.request("editor", "PATCH", f"{VENUES}/{made['id']}", json={"notes": "Privat"})
    async with api.maker() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT target_type, data FROM audit_entry WHERE action = 'config_change' ORDER BY id"
                )
            )
        ).all()
    assert [r.target_type for r in rows] == ["venue", "venue"]
    assert rows[1].data == {"fields": ["notes"]}
    assert "Geheimweg" not in str(rows) and "Privat" not in str(rows)


async def test_category_description_is_set_cleared_and_validated(api: Api) -> None:
    made = await api.request(
        "editor",
        "POST",
        CATS,
        json={
            "slug": "e2e-beschreibung",
            "name": "Beschreibung",
            "kind": "format",
            "description": "Kurz",
        },
    )
    assert made.status_code == 201 and made.json()["description"] == "Kurz"
    url = f"{CATS}/{made.json()['id']}"
    patched = await api.request("editor", "PATCH", url, json={"description": "  Neu und kurz  "})
    assert patched.status_code == 200 and patched.json()["description"] == "Neu und kurz"
    cleared = await api.request("editor", "PATCH", url, json={"description": None})
    assert cleared.status_code == 200 and cleared.json()["description"] is None
    for bad in ("x" * 301, "a\x07b"):
        refused = await api.request("editor", "PATCH", url, json={"description": bad})
        assert refused.status_code == 422, bad
    rows = await api.sql(
        "SELECT description FROM public_category_v WHERE slug = 'e2e-beschreibung'"
    )
    assert rows == [(None,)]
    await api.request("editor", "PATCH", url, json={"description": "Öffentlich"})
    rows = await api.sql(
        "SELECT description FROM public_category_v WHERE slug = 'e2e-beschreibung'"
    )
    assert rows == [("Öffentlich",)]
    await api.sql("DELETE FROM category WHERE slug = 'e2e-beschreibung'")
