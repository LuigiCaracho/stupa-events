"""The library list and "adopt", and the template list: rights live in the SQL."""

from __future__ import annotations

import pytest

from tests.integration.archive.fixture import archived_movienight, ok
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration
FILES = (("other", "shared", True), ("other", "org", True))


async def library(api: Api, user: str = "member", **params: object) -> dict:
    return await ok(await api.request(user, "GET", "/api/library", params={"limit": 50, **params}))


async def test_library_lists_only_what_was_shared_in_archived_dossiers(api: Api) -> None:
    eid = await archived_movienight(api, files=FILES)
    live = await api.to_state("published", title="Noch live")
    await api.sql(
        "INSERT INTO document (event_id, kind, title, body_md, visibility) "
        "VALUES (:e, 'howto', 'Live-Anleitung', 'x', 'shared')",
        e=live["id"],
    )
    await api.sql(
        "INSERT INTO attachment (event_id, display_name, storage_name, mime, size_bytes, sha256, "
        "scan_status, visibility, kind) VALUES (:e, :n, 'w', 'application/pdf', 1, :h, :s, 'shared', 'other')",
        e=eid,
        n="wartet.pdf",
        h="aa",
        s="pending",
    )
    page = await library(api)
    titles = sorted((i["kind"], i["title"]) for i in page["items"])
    assert titles == [
        ("attachment", "plan.pdf"),
        ("document", "Anleitung"),
        ("document", "Einladung"),
    ]
    assert page["total"] == 3 and {f["value"] for f in page["facets"]["kind"]} == {
        "document",
        "attachment",
    }
    doc = next(i for i in page["items"] if i["title"] == "Anleitung")
    assert doc["source"]["type"] == "event" and doc["source"]["organization"]["slug"] == "fsi"
    assert doc["source"]["own"] is False and doc["subKind"] == "howto"
    assert doc["categories"][0]["slug"] == "kino" and "bodyMd" not in str(page)
    mine = await library(api, "organizer-fsi")
    assert all(i["source"]["own"] for i in mine["items"])
    assert (await api.request(None, "GET", "/api/library")).status_code == 401


async def test_library_has_the_master_howto_and_filters(api: Api) -> None:
    eid = await archived_movienight(api, files=FILES)
    await ok(
        await api.request(
            "editor", "POST", "/api/formats/movienight/howto", json={"fromEventId": eid}
        ),
        201,
    )
    page = await library(api)
    master = next(i for i in page["items"] if i["source"]["type"] == "format")
    assert master["source"]["title"] == "Movienight" and master["source"]["startsAt"] is None
    only_files = await library(api, kind="attachment")
    assert [i["title"] for i in only_files["items"]] == ["plan.pdf"]
    only_docs = await library(api, kind="document")
    assert only_docs["total"] == 3
    assert (await library(api, organization="makers"))["total"] == 0
    assert (await library(api, category="kino"))["total"] >= 3
    assert (await library(api, category="fachschaft"))["total"] == 0
    assert (await library(api, format="movienight"))["total"] == 4
    year = master["updatedAt"][:4]
    assert (await library(api, year=int(year)))["total"] >= 1


async def test_library_search_uses_text_search_for_documents_and_ilike_for_files(api: Api) -> None:
    await archived_movienight(api, files=FILES)
    docs = await library(api, q="Einladung")
    assert [i["title"] for i in docs["items"]] == ["Einladung"]
    typo = await library(api, q="Anleitnug")
    assert [i["title"] for i in typo["items"]] == ["Anleitung"]
    files = await library(api, q="plan")
    assert [i["title"] for i in files["items"]] == ["plan.pdf"]
    wildcard = await library(api, q="%%")
    assert wildcard["total"] == 0
    short = await library(api, q="a")
    assert short["total"] == 0 and short["facets"]["kind"] == []
    only_docs = await library(api, q="plan", kind="document")
    assert only_docs["total"] == 0


async def test_adopt_copies_text_only_and_turns_a_second_howto_into_a_note(api: Api) -> None:
    await archived_movienight(api, files=FILES)
    howto = next(i for i in (await library(api))["items"] if i["title"] == "Anleitung")
    target = await api.create_event(user="organizer-makers", org="makers", title="Eigener Abend")
    url = f"/api/library/documents/{howto['id']}/adopt"
    first = await ok(
        await api.request("organizer-makers", "POST", url, json={"eventId": target["id"]}), 201
    )
    assert first["kind"] == "howto" and first["rev"] == 1 and first["verifiedAt"] is None
    assert first["carryOver"] is True and first["bodyMd"].startswith("# Aufbau")
    second = await ok(
        await api.request("organizer-makers", "POST", url, json={"eventId": target["id"]}), 201
    )
    assert second["kind"] == "notes"
    revision = await ok(
        await api.request("organizer-makers", "GET", f"/api/documents/{first['id']}/revisions")
    )
    assert revision[0]["changeNote"] == "Aus Bibliothek übernommen: Anleitung"
    assert (await api.sql("SELECT count(*) FROM attachment WHERE event_id = :e", e=target["id"]))[
        0
    ][0] == 0
    denied = await api.request("member", "POST", url, json={"eventId": target["id"]})
    assert denied.status_code == 403
    foreign = await api.request("organizer-fsi", "POST", url, json={"eventId": target["id"]})
    assert foreign.status_code == 404


async def test_adopt_refuses_documents_outside_the_library(api: Api) -> None:
    eid = await archived_movienight(api)
    rows = await api.sql("SELECT id, kind FROM document WHERE event_id = :e", e=eid)
    ids = {kind: str(i) for i, kind in rows}
    target = await api.create_event(title="Ziel")
    for kind in ("notes", "retrospective"):
        refused = await api.request(
            "organizer-fsi",
            "POST",
            f"/api/library/documents/{ids[kind]}/adopt",
            json={"eventId": target["id"]},
        )
        assert refused.status_code == 404, kind
    await api.sql("UPDATE document SET visibility = 'team' WHERE id = :i", i=ids["howto"])
    hidden = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/library/documents/{ids['howto']}/adopt",
        json={"eventId": target["id"]},
    )
    assert hidden.status_code == 404
    await api.sql("UPDATE document SET visibility = 'shared' WHERE id = :i", i=ids["howto"])
    await api.sql("UPDATE event SET state = 'draft' WHERE id = :e", e=eid)
    not_archived = await api.request(
        "organizer-fsi",
        "POST",
        f"/api/library/documents/{ids['howto']}/adopt",
        json={"eventId": target["id"]},
    )
    assert not_archived.status_code == 404


async def test_template_list(api: Api) -> None:
    eid = await archived_movienight(api)
    own_live = await api.to_state("published", title="Movienight: Live")
    mine = await ok(await api.request("organizer-fsi", "GET", "/api/templates"))
    titles = {c["title"]: c for c in mine["items"]}
    assert set(titles) == {"Movienight: Whiplash", "Movienight: Live"}
    card = titles["Movienight: Whiplash"]
    assert card["foreign"] is False and card["attendance"] == 87 and card["hasHowto"] is True
    assert card["sharedDocuments"] == 2 and card["checklistItems"] > 0
    assert card["howtoUnverified"] is False and card["format"]["slug"] == "movienight"
    assert card["categories"][0]["slug"] == "kino"
    theirs = await ok(await api.request("organizer-makers", "GET", "/api/templates"))
    assert [c["title"] for c in theirs["items"]] == ["Movienight: Whiplash"]
    assert theirs["items"][0]["foreign"] is True and own_live["id"] not in str(theirs)
    searched = await ok(
        await api.request("organizer-fsi", "GET", "/api/templates", params={"q": "whiplash"})
    )
    assert [c["id"] for c in searched["items"]] == [eid]
    filtered = await ok(
        await api.request(
            "organizer-fsi",
            "GET",
            "/api/templates",
            params={"organization": "fsi", "format": "movienight", "category": "kino"},
        )
    )
    assert filtered["total"] == 1
    nothing = await ok(
        await api.request("organizer-fsi", "GET", "/api/templates", params={"q": "x"})
    )
    assert nothing["total"] == 0
    assert (
        await api.request("organizer-fsi", "GET", "/api/templates", params={"year": 1999})
    ).json()["total"] == 0
    assert (await api.request(None, "GET", "/api/templates")).status_code == 401


async def test_templates_are_ordered_by_the_freshness_of_their_format(api: Api) -> None:
    old = await archived_movienight(api, title="Alte Ausgabe", days_ago=200)
    fresh = await archived_movienight(api, title="Frische Ausgabe", days_ago=90)
    await api.sql(
        "UPDATE event SET format_id = (SELECT id FROM format WHERE slug = 'campusfest') WHERE id = :e",
        e=fresh,
    )
    await api.sql("UPDATE format SET last_verified_at = now() WHERE slug = 'campusfest'")
    page = await ok(await api.request("organizer-fsi", "GET", "/api/templates"))
    assert [c["id"] for c in page["items"]] == [fresh, old]
