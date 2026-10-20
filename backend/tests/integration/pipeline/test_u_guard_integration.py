"""U-GUARD-05, 07, 08 and 13: the cases that need the database or HTTP."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy.exc import DBAPIError

from tests.integration.events.harness import Api
from tests.integration.pipeline.test_four_eyes import stupa_in_review

pytestmark = pytest.mark.integration


async def test_u_guard_05_a_foreign_organization_gets_404(api: Api) -> None:
    event = await api.to_state("in_review")
    for tid in ("T04", "T05"):
        assert (await api.fire("organizer-makers", event["id"], tid)).status_code == 404
        guards = await api.request(
            "organizer-makers", "GET", f"/api/events/{event['id']}/guards/{tid}"
        )
        assert guards.status_code == 404


async def test_u_guard_07_pending_and_infected_posters_block_and_are_quarantined(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    poster = await api.upload_poster("organizer-fsi", eid)
    assert poster.status_code == 201
    await api.fire("organizer-fsi", eid, "T02")
    pending = await api.fire("editor", eid, "T04")
    assert pending.status_code == 422 and pending.json()["code"] == "image_required"
    assert await api.process_poster(poster.json()["id"], signature="Eicar-Test") == "infected"
    infected = await api.fire("editor", eid, "T04")
    assert infected.status_code == 422 and infected.json()["code"] == "image_required"
    file = await api.request("editor", "GET", f"/api/events/{eid}/poster/file")
    assert file.status_code == 409 and file.json()["code"] == "quarantined"


async def test_u_guard_08_the_poster_of_a_live_event_stays(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    up = await api.upload_poster("organizer-fsi", eid)
    await api.process_poster(up.json()["id"])
    await api.fire("organizer-fsi", eid, "T02")
    await api.fire("editor", eid, "T04")
    await api.fire("editor", eid, "T05")
    replace = await api.upload_poster("editor", eid, altText="Anderes")
    assert replace.status_code == 201
    assert (await api.get("editor", eid))["poster"]["id"] == up.json()["id"]
    with pytest.raises(DBAPIError) as caught:
        await api.sql("UPDATE event SET hero_attachment_id = NULL WHERE id = :i", i=eid)
    assert getattr(caught.value.orig, "sqlstate", None) == "23514"


async def test_u_guard_13_two_concurrent_approvals_one_wins(api: Api) -> None:
    eid = await stupa_in_review(api)
    rev = (await api.get("editor", eid))["rev"]
    first, second = await asyncio.gather(
        api.fire("approver2-stupa", eid, "T04", if_match_rev=rev),
        api.fire("editor", eid, "T04", if_match_rev=rev),
    )
    codes = sorted([first.status_code, second.status_code])
    assert codes == [200, 409]
    loser = first if first.status_code == 409 else second
    assert loser.json()["code"] in {"conflict", "invalid_transition"}
    rows = await api.sql("SELECT count(*) FROM event_status_event WHERE transition_id = 'T04'")
    assert rows == [(1,)]


async def test_a_depicted_person_needs_a_consent_note(api: Api) -> None:
    event = await api.to_state("planning")
    eid = event["id"]
    missing = await api.upload_poster("organizer-fsi", eid, personsDepicted="true")
    assert missing.status_code == 422 and missing.json()["code"] == "consent_missing"
    up = await api.upload_poster(
        "organizer-fsi", eid, personsDepicted="true", consentNote="Einwilligung liegt vor"
    )
    assert up.status_code == 201 and up.json()["personsDepicted"] is True
    await api.sql("UPDATE attachment SET consent_note = NULL WHERE id = :i", i=up.json()["id"])
    await api.process_poster(up.json()["id"])
    await api.fire("organizer-fsi", eid, "T02")
    refused = await api.fire("editor", eid, "T04")
    assert refused.status_code == 422 and refused.json()["code"] == "rights_incomplete"
    assert refused.json()["reasons"][0]["fixAction"] == "fill_rights"
    ok = await api.upload_poster(
        "editor", eid, personsDepicted="true", consentNote="Einwilligung liegt vor"
    )
    assert ok.status_code == 201
    await api.process_poster(ok.json()["id"])
    assert (await api.fire("editor", eid, "T04")).status_code == 200
