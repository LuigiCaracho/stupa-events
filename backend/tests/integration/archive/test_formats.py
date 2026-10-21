"""Formats (I18): list, page, rights, master howto, verification, new edition, save as format."""

from __future__ import annotations

from typing import Any

import pytest

from tests.integration.archive.fixture import archived_movienight, ok
from tests.integration.events.harness import Api, future

pytestmark = pytest.mark.integration


def new_format(api: Api, _slug: str = "spieleabend", **over: Any) -> dict[str, Any]:
    return {
        "slug": _slug,
        "title": "Spieleabend",
        "organizationId": api.org_ids["fsi"],
        "descriptionMd": "Brettspiele.",
        **over,
    }


async def test_the_seeded_formats_are_listed_with_their_editions(api: Api) -> None:
    await archived_movienight(api)
    page = await ok(await api.request("member", "GET", "/api/formats", params={"limit": 50}))
    assert page["total"] == 7
    cards = {c["slug"]: c for c in page["items"]}
    assert cards["movienight"]["editions"] == 1
    assert cards["movienight"]["lastEdition"]["title"] == "Movienight: Whiplash"
    assert cards["movienight"]["howtoStale"] is False
    assert cards["campusfest"]["editions"] == 0 and cards["campusfest"]["lastEdition"] is None
    assert cards["campusfest"]["howtoStale"] is True
    found = await ok(await api.request("member", "GET", "/api/formats", params={"q": "campus"}))
    assert [c["slug"] for c in found["items"]] == ["campusfest"]
    own = await ok(
        await api.request("member", "GET", "/api/formats", params={"organization": "praesidium"})
    )
    assert [c["slug"] for c in own["items"]] == ["offenes-praesidium"]
    assert (await api.request(None, "GET", "/api/formats")).status_code == 401


async def test_the_format_page_shows_costs_to_the_own_organization_only(api: Api) -> None:
    await archived_movienight(api)
    mine = await ok(await api.request("organizer-fsi", "GET", "/api/formats/movienight"))
    theirs = await ok(await api.request("organizer-makers", "GET", "/api/formats/movienight"))
    assert mine["editions"][0]["costsCents"] == 24500 and mine["editions"][0]["foreign"] is False
    assert theirs["editions"][0]["costsCents"] is None and theirs["editions"][0]["foreign"] is True
    assert theirs["editions"][0]["attendance"] == 87
    assert theirs["checklist"]["profile"] == "generic" and theirs["checklist"]["items"]
    assert {m["title"] for m in theirs["mailTemplates"]} == {"Einladung"}
    assert theirs["defaults"]["durationMinutes"] == 180 and theirs["masterHowto"] is None
    assert (await api.request("member", "GET", "/api/formats/gibt-es-nicht")).status_code == 404


async def test_create_and_patch_rules(api: Api) -> None:
    made = await api.request("organizer-fsi", "POST", "/api/formats", json=new_format(api))
    assert made.status_code == 201 and made.headers["location"] == "/api/formats/spieleabend"
    again = await api.request("organizer-fsi", "POST", "/api/formats", json=new_format(api))
    assert again.status_code == 409 and again.json()["code"] == "slug_taken"
    for bad in (
        {"slug": "Gross Klein"},
        {"title": "x\ny"},
        {"title": ""},
        {"defaults": {"durationMinutes": 5}},
        {"defaults": {"categoryId": "00000000-0000-0000-0000-000000000000"}},
        {"defaults": {"venueId": "00000000-0000-0000-0000-000000000000"}},
    ):
        response = await api.request(
            "organizer-fsi", "POST", "/api/formats", json=new_format(api, "x-1", **bad)
        )
        assert response.status_code == 422, bad
    foreign_org = await api.request(
        "organizer-makers", "POST", "/api/formats", json=new_format(api, "x-2")
    )
    assert foreign_org.status_code == 403
    assert (
        await api.request("viewer-fsi", "POST", "/api/formats", json=new_format(api, "x-3"))
    ).status_code == 403
    unknown_org = await api.request(
        "editor",
        "POST",
        "/api/formats",
        json=new_format(api, "x-4", organizationId="00000000-0000-0000-0000-000000000000"),
    )
    assert unknown_org.status_code == 404
    editor = await api.request("editor", "POST", "/api/formats", json=new_format(api, "x-5"))
    assert editor.status_code == 201
    kino = api.category_ids["kino"]
    patched = await ok(
        await api.request(
            "organizer-fsi",
            "PATCH",
            "/api/formats/spieleabend",
            json={
                "title": "Quizabend",
                "descriptionMd": None,
                "active": False,
                "defaults": {
                    "categoryId": kino,
                    "durationMinutes": 240,
                    "checklistProfile": "party",
                },
            },
        )
    )
    assert patched["title"] == "Quizabend" and patched["active"] is False
    assert patched["defaults"]["checklistProfile"] == "party" and patched["descriptionMd"] is None
    hidden = await ok(await api.request("member", "GET", "/api/formats", params={"q": "Quizabend"}))
    assert hidden["items"] == []
    assert (await api.request("member", "GET", "/api/formats/spieleabend")).status_code == 200
    stranger = await api.request(
        "organizer-makers", "PATCH", "/api/formats/spieleabend", json={"title": "X"}
    )
    assert stranger.status_code == 403


async def test_master_howto_scaffold_copy_and_verification(api: Api) -> None:
    eid = await archived_movienight(api)
    url = "/api/formats/movienight/howto"
    empty = await api.request("organizer-fsi", "POST", "/api/formats/caipi-night/howto", json={})
    assert empty.status_code == 201 and empty.json()["bodyMd"].startswith(
        "# Anleitung: Caipi Night"
    )
    twice = await api.request("organizer-fsi", "POST", "/api/formats/caipi-night/howto", json={})
    assert twice.status_code == 409 and twice.json()["code"] == "already_exists"
    plain = await api.to_state("draft")
    no_howto = await api.request("organizer-fsi", "POST", url, json={"fromEventId": plain["id"]})
    assert no_howto.status_code == 422 and no_howto.json()["code"] == "no_howto"
    stranger = await api.request("organizer-makers", "POST", url, json={"fromEventId": eid})
    assert stranger.status_code == 403
    copied = await ok(
        await api.request("organizer-fsi", "POST", url, json={"fromEventId": eid}), 201
    )
    assert copied["title"] == "Anleitung" and copied["verifiedAt"] is None and copied["rev"] == 1
    page = await ok(await api.request("member", "GET", "/api/formats/movienight"))
    assert page["masterHowto"]["bodyMd"].startswith("# Aufbau")
    verified = await ok(
        await api.request("organizer-fsi", "POST", "/api/formats/movienight/verify")
    )
    assert verified["howtoStale"] is False and verified["masterHowto"]["verifiedAt"]
    other = await api.request("organizer-makers", "POST", "/api/formats/movienight/verify")
    assert other.status_code == 403
    doc = page["masterHowto"]["id"]
    mine = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/documents/{doc}",
        json={"bodyMd": "# Neu"},
        headers={"If-Match": '"1"'},
    )
    assert mine.status_code == 200 and mine.json()["formatId"] and mine.json()["eventId"] is None
    nope = await api.request(
        "organizer-makers",
        "PUT",
        f"/api/documents/{doc}",
        json={"bodyMd": "x"},
        headers={"If-Match": '"2"'},
    )
    assert nope.status_code == 403
    read = await api.request("member", "GET", f"/api/documents/{doc}")
    assert read.status_code == 200
    draft = await api.request(
        "organizer-fsi",
        "PUT",
        f"/api/documents/{doc}/draft",
        json={"bodyMd": "entwurf"},
        headers={"If-Match": '"2"'},
    )
    assert draft.status_code == 200


async def test_a_stale_format_is_flagged_after_twelve_months(api: Api) -> None:
    await api.sql(
        "UPDATE format SET last_verified_at = now() - interval '13 months' WHERE slug = 'movienight'"
    )
    page = await ok(await api.request("member", "GET", "/api/formats/movienight"))
    assert page["howtoStale"] is True
    await api.sql(
        "UPDATE format SET last_verified_at = now() - interval '2 months' WHERE slug = 'movienight'"
    )
    assert (await ok(await api.request("member", "GET", "/api/formats/movienight")))[
        "howtoStale"
    ] is False


async def test_new_edition_clones_the_newest_template_or_builds_from_the_defaults(api: Api) -> None:
    fresh = await api.request(
        "organizer-fsi",
        "POST",
        "/api/formats/fsi-lan-party/new-edition",
        json={"startsAt": future(30).isoformat()},
    )
    assert fresh.status_code == 201, fresh.text
    body = fresh.json()
    event = body["event"]
    assert body["report"] == [] and event["state"] == "draft" and event["title"] == "FSI LAN-Party"
    assert event["format"]["slug"] == "fsi-lan-party"
    assert event["primaryCategory"]["slug"] == "lanparty"
    assert event["checklistRecomputed"] > 0
    items = (
        await api.request("organizer-fsi", "GET", f"/api/events/{event['id']}/checklist")
    ).json()
    assert any(i["text"].startswith("Sicherheitskonzept") for i in items["items"])
    source = await archived_movienight(api)
    cloned = await ok(
        await api.request(
            "organizer-fsi",
            "POST",
            "/api/formats/movienight/new-edition",
            json={"startsAt": future(40).isoformat()},
        ),
        201,
    )
    assert cloned["event"]["derivedFromId"] == source and cloned["report"]
    assert cloned["event"]["title"] == "Movienight: Whiplash"
    makers = await ok(
        await api.request(
            "organizer-makers",
            "POST",
            "/api/formats/fsi-game-together/new-edition",
            json={"startsAt": future(40).isoformat()},
        ),
        201,
    )
    assert makers["event"]["organization"]["slug"] == "makers"
    nobody = await api.request(
        "viewer-fsi",
        "POST",
        "/api/formats/movienight/new-edition",
        json={"startsAt": future(40).isoformat()},
    )
    assert nobody.status_code == 403
    assert (
        await api.request(
            "organizer-fsi",
            "POST",
            "/api/formats/nope/new-edition",
            json={"startsAt": future(40).isoformat()},
        )
    ).status_code == 404


async def test_save_as_format(api: Api) -> None:
    eid = await archived_movienight(api, title="Spiel am Abend")
    event = await api.get("organizer-fsi", eid)
    await api.sql("UPDATE event SET format_id = NULL WHERE id = :e", e=eid)
    body = {"slug": "abend-spiel", "title": "Spiel am Abend"}
    saved = await ok(
        await api.request("organizer-fsi", "POST", f"/api/events/{eid}/save-as-format", json=body),
        201,
    )
    assert saved["defaults"]["categoryId"] == event["primaryCategory"]["id"]
    assert (
        saved["defaults"]["durationMinutes"] == 180
        and saved["defaults"]["checklistProfile"] == "generic"
    )
    assert (
        saved["masterHowto"]["verifiedAt"] is None and saved["masterHowto"]["title"] == "Anleitung"
    )
    assert [e["id"] for e in saved["editions"]] == [eid]
    assert (await api.get("organizer-fsi", eid))["format"]["slug"] == "abend-spiel"
    again = await api.request(
        "organizer-fsi", "POST", f"/api/events/{eid}/save-as-format", json=body
    )
    assert again.status_code == 409 and again.json()["code"] == "already_in_format"
    other = await api.to_state("draft", title="Zweiter")
    taken = await api.request(
        "organizer-fsi", "POST", f"/api/events/{other['id']}/save-as-format", json=body
    )
    assert taken.status_code == 409 and taken.json()["code"] == "slug_taken"
    override = await ok(
        await api.request(
            "organizer-fsi",
            "POST",
            f"/api/events/{other['id']}/save-as-format",
            json={"slug": "zweiter", "title": "Zweiter", "defaults": {"durationMinutes": 90}},
        ),
        201,
    )
    assert override["defaults"]["durationMinutes"] == 90 and override["masterHowto"] is None
    proposal = await api.create_event(title="Altlast")
    await api.sql("UPDATE event SET organization_id = NULL WHERE id = :e", e=proposal["id"])
    no_org = await api.request(
        "editor",
        "POST",
        f"/api/events/{proposal['id']}/save-as-format",
        json={"slug": "v", "title": "V"},
    )
    assert no_org.status_code == 422 and no_org.json()["code"] == "organization_required"
    third = await api.to_state("draft", title="Dritter")
    denied = await api.request(
        "organizer-makers",
        "POST",
        f"/api/events/{third['id']}/save-as-format",
        json={"slug": "d", "title": "D"},
    )
    assert denied.status_code == 404
    submitter = await api.request(
        "submitter-fsi",
        "POST",
        f"/api/events/{third['id']}/save-as-format",
        json={"slug": "d", "title": "D"},
    )
    assert submitter.status_code == 403


async def test_put_event_format(api: Api) -> None:
    event = await api.create_event()
    eid = event["id"]
    url = f"/api/events/{eid}/format"
    assert (
        await api.request("organizer-fsi", "PUT", url, json={"slug": "movienight"})
    ).status_code == 428
    headers = {"If-Match": f'"{event["rev"]}"'}
    set_ = await ok(
        await api.request("organizer-fsi", "PUT", url, json={"slug": "movienight"}, headers=headers)
    )
    assert set_["format"]["slug"] == "movienight"
    stale = await api.request("organizer-fsi", "PUT", url, json={"slug": None}, headers=headers)
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    fresh = {"If-Match": f'"{set_["rev"]}"'}
    unknown = await api.request("organizer-fsi", "PUT", url, json={"slug": "nope"}, headers=fresh)
    assert unknown.status_code == 404
    cleared = await ok(
        await api.request("organizer-fsi", "PUT", url, json={"slug": None}, headers=fresh)
    )
    assert cleared["format"] is None and cleared["formatId"] is None


async def test_patch_touches_only_the_given_fields(api: Api) -> None:
    url = "/api/formats/spieleabend"
    await ok(await api.request("organizer-fsi", "POST", "/api/formats", json=new_format(api)), 201)
    kino = api.category_ids["kino"]
    for body in (
        {"title": None},
        {"defaults": None},
        {"active": None},
        {"descriptionMd": "Neu."},
        {"defaults": {"categoryId": kino}},
        {"active": False},
        {"title": "Neu"},
    ):
        assert (await api.request("organizer-fsi", "PATCH", url, json=body)).status_code == 200
    final = await ok(await api.request("organizer-fsi", "GET", url))
    assert final["title"] == "Neu" and final["active"] is False and final["descriptionMd"] == "Neu."
