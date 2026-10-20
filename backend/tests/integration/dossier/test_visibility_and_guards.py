"""Visibility per role over HTTP, tab counters, guard snapshots and the public feed canary."""

from __future__ import annotations

import pytest

from app.modules.events.access import guard_snapshot, poster_of
from app.modules.events.card_extras import load_card_extras
from app.modules.events.models import Event
from tests._support import samples
from tests._support.factories import png_bytes
from tests.integration.dossier.helpers import live_event, planning_event, upload
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration

VISIBLE = {
    "organizer-fsi": {"q.pdf", "o.png", "t.png", "h.md"},
    "approver-fsi": {"q.pdf", "o.png", "t.png", "h.md"},
    "editor": {"q.pdf", "o.png", "t.png", "h.md"},
    "admin": {"q.pdf", "o.png", "t.png", "h.md"},
    "submitter-fsi": {"q.pdf", "o.png", "h.md"},
    "stupa": {"q.pdf", "o.png", "h.md"},
    "viewer-fsi": {"o.png", "h.md"},
}


async def seed_files(api: Api) -> str:
    eid = await planning_event(api)
    for kind, name, data, vis in (
        ("quote", "q.pdf", samples.pdf_bytes(), "org"),
        ("other", "o.png", png_bytes(), "org"),
        ("other", "t.png", png_bytes(), "team"),
        ("howto_file", "h.md", b"# x", "shared"),
    ):
        assert (
            await upload(api, "organizer-fsi", eid, kind, name, data, visibility=vis)
        ).status_code == 201
    return eid


@pytest.mark.parametrize("user", sorted(VISIBLE))
async def test_attachment_visibility_matrix_http(api: Api, user: str) -> None:
    eid = await seed_files(api)
    listed = await api.request(user, "GET", f"/api/events/{eid}/attachments")
    assert listed.status_code == 200
    assert {a["displayName"] for a in listed.json()} == VISIBLE[user]
    by_name = {a["displayName"]: a["id"] for a in listed.json()}
    every = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/attachments")).json()
    for row in every:
        name = row["displayName"]
        status = (
            await api.request(user, "GET", f"/api/attachments/{row['id']}/download")
        ).status_code
        assert status == (409 if name in by_name else 404), (user, name)


@pytest.mark.parametrize("user", ["organizer-makers", "approver-stupa", "member", "nobody"])
async def test_foreign_organizations_see_nothing_of_the_dossier(api: Api, user: str) -> None:
    eid = await seed_files(api)
    for path in (
        f"/api/events/{eid}/attachments",
        f"/api/events/{eid}/dossier-counts",
        f"/api/events/{eid}/documents",
        f"/api/events/{eid}/checklist",
        f"/api/events/{eid}/comments",
        f"/api/events/{eid}/mail-templates",
    ):
        assert (await api.request(user, "GET", path)).status_code == 404, (user, path)


async def test_counts_hide_the_restricted_counter(api: Api) -> None:
    eid = await seed_files(api)
    await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/quotes",
        json={"grp": "A", "vendor": "B", "amountCents": 1},
    )
    full = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/dossier-counts")).json()
    assert full == {
        "attachments": 4,
        "quotes": 1,
        "howto": 0,
        "openChecklist": 0,
        "mailTemplates": 0,
        "openComments": 0,
    }
    viewer = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/dossier-counts")).json()
    assert "quotes" not in viewer and viewer["attachments"] == 2


async def test_snapshot_builders_set_m4_fields(api: Api) -> None:
    eid = await planning_event(api)
    await api.request(
        "organizer-fsi", "POST", f"/api/events/{eid}/checklist/apply-template", json={}
    )
    await api.request(
        "editor",
        "POST",
        f"/api/events/{eid}/comments",
        json={"bodyMd": "?", "anchor": {"field": "hero"}},
    )
    await upload(api, "organizer-fsi", eid, "howto_file", "h.md", b"# x", visibility="shared")
    await api.upload_poster("organizer-fsi", eid, data=png_bytes())
    async with api.maker() as session:
        event = await session.get(Event, eid)
        assert event is not None
        poster = await poster_of(session, event)
        single = await guard_snapshot(session, event, poster)
        card = (await load_card_extras(session, [event])).snapshot(event, poster)
    assert single == card
    assert single.open_comments == 1 and single.open_hero_comments == 1
    assert single.open_required_checklist == 1
    assert single.quarantined_attachments == 1


async def test_a_printed_date_of_another_year_asks_for_the_flyer_check(api: Api) -> None:
    eid = await planning_event(api)
    out = (await api.upload_poster("organizer-fsi", eid, data=png_bytes())).json()
    await api.sql("UPDATE attachment SET contains_date = true, dated_for = '2019-05-05'")
    assert await api.process_poster(out["id"]) == "clean"
    async with api.maker() as session:
        event = await session.get(Event, eid)
        assert event is not None
        snapshot = await guard_snapshot(session, event, await poster_of(session, event))
    assert snapshot.poster is not None and snapshot.poster.reused_in_other_year
    confirmed = await api.action("organizer-fsi", eid, "confirm-flyer")
    assert confirmed.status_code == 200
    row = await api.sql("SELECT flyer_date_confirmed_by FROM attachment WHERE id = :i", i=out["id"])
    assert row[0][0] == "sub-org-fsi"


async def test_public_feed_unchanged(api: Api) -> None:
    live = await live_event(api)
    eid = live["id"]
    await upload(
        api,
        "organizer-fsi",
        eid,
        "other",
        "geheim-name.pdf",
        samples.pdf_bytes(),
        visibility="shared",
    )
    await api.request(
        "organizer-fsi",
        "POST",
        f"/api/events/{eid}/quotes",
        json={"grp": "A", "vendor": "Zulieferer", "amountCents": 987654},
    )
    await api.request(
        "editor", "POST", f"/api/events/{eid}/comments", json={"bodyMd": "internes Wort"}
    )
    text = (await api.request(None, "GET", "/api/public/feed/events")).text
    for needle in ("geheim-name", "Zulieferer", "987654", "internes Wort", "attachment", "comment"):
        assert needle not in text, needle
