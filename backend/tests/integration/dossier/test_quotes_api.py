"""Comparison quotes: groups, one selected per group, and who may see the amounts."""

from __future__ import annotations

import json

import pytest

from tests._support import samples
from tests.integration.dossier.helpers import draft_event, upload
from tests.integration.events.harness import Api

pytestmark = pytest.mark.integration


async def add_quote(api: Api, eid: str, user: str = "organizer-fsi", **over: object):  # noqa: ANN201
    body = {"grp": "Technik", "vendor": "Licht GmbH", "amountCents": 120_000, **over}
    return await api.request(user, "POST", f"/api/events/{eid}/quotes", json=body)


async def test_groups_cheapest_selection_and_totals(api: Api) -> None:
    eid = await draft_event(api)
    a = (await add_quote(api, eid)).json()
    b = (await add_quote(api, eid, vendor="Ton AG", amountCents=90_000)).json()
    c = (await add_quote(api, eid, grp="Catering", vendor="Brot", amountCents=30_000)).json()
    usd = (
        await add_quote(api, eid, grp="Merch", vendor="US", amountCents=5_000, currency="USD")
    ).json()
    for quote in (a, b, c, usd):
        assert (
            await api.request("organizer-fsi", "POST", f"/api/quotes/{quote['id']}/select")
        ).status_code == 200
    swap = await api.request("organizer-fsi", "POST", f"/api/quotes/{a['id']}/select")
    assert swap.status_code == 200
    data = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/quotes")).json()
    groups = {g["grp"]: g for g in data["groups"]}
    assert groups["Technik"]["cheapestId"] == b["id"] and groups["Technik"]["selectedId"] == a["id"]
    assert data["selectedTotalCents"] == 150_000 and data["selectedTotalCurrency"] == "EUR"
    assert data["suggestedBudgetCents"] == 150_000
    assert data["otherCurrencies"] == [{"currency": "USD", "totalCents": 5_000}]
    rows = await api.sql("SELECT count(*) FROM quote WHERE selected AND grp = 'Technik'")
    assert rows[0][0] == 1


async def test_expired_quotes_cannot_be_selected_and_hidden_ones_vanish(api: Api) -> None:
    eid = await draft_event(api)
    old = (await add_quote(api, eid, validUntil="2020-01-01")).json()
    assert old["expired"] is True
    blocked = await api.request("organizer-fsi", "POST", f"/api/quotes/{old['id']}/select")
    assert blocked.status_code == 409 and blocked.json()["code"] == "quote_expired"
    gone = await api.request("organizer-fsi", "DELETE", f"/api/quotes/{old['id']}")
    assert gone.status_code == 204
    data = (await api.request("organizer-fsi", "GET", f"/api/events/{eid}/quotes")).json()
    assert data["groups"] == []
    shown = (
        await api.request("organizer-fsi", "GET", f"/api/events/{eid}/quotes?includeRetired=true")
    ).json()
    assert shown["groups"][0]["quotes"][0]["retiredAt"] is not None


async def test_a_quote_file_must_be_a_quote_attachment_of_the_dossier(api: Api) -> None:
    eid = await draft_event(api)
    other = await draft_event(api)
    quote_file = (
        await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())
    ).json()
    foreign = (
        await upload(api, "organizer-fsi", other, "quote", "b.pdf", samples.pdf_bytes())
    ).json()
    plain = (await upload(api, "organizer-fsi", eid, "other", "c.pdf", samples.pdf_bytes())).json()
    assert (await add_quote(api, eid, attachmentId=quote_file["id"])).status_code == 201
    assert (await add_quote(api, eid, attachmentId=foreign["id"])).status_code == 422
    assert (await add_quote(api, eid, attachmentId=plain["id"])).status_code == 422


async def test_quotes_are_invisible_to_foreign_organizations_and_403_without_the_right(
    api: Api,
) -> None:
    eid = await draft_event(api)
    quote = (await add_quote(api, eid)).json()
    file = (await upload(api, "organizer-fsi", eid, "quote", "a.pdf", samples.pdf_bytes())).json()
    assert await api.process_poster(file["id"]) == "clean"
    for user in ("organizer-makers",):
        assert (await api.request(user, "GET", f"/api/events/{eid}/quotes")).status_code == 404, (
            user
        )
        for method, path in (
            ("POST", f"/api/quotes/{quote['id']}/select"),
            ("PATCH", f"/api/quotes/{quote['id']}"),
            ("DELETE", f"/api/quotes/{quote['id']}"),
        ):
            assert (await api.request(user, method, path, json={})).status_code == 404, (user, path)
        download = await api.request(user, "GET", f"/api/attachments/{file['id']}/download")
        assert download.status_code == 404, user
    for user in ("member", "nobody"):
        assert (await api.request(user, "GET", f"/api/events/{eid}/quotes")).status_code == 404, (
            user
        )
        assert (
            await api.request(user, "POST", f"/api/quotes/{quote['id']}/select")
        ).status_code == 403
    denied = await api.request("viewer-fsi", "GET", f"/api/events/{eid}/quotes")
    assert denied.status_code == 403 and "120000" not in denied.text
    assert (
        await api.request("viewer-fsi", "POST", f"/api/quotes/{quote['id']}/select")
    ).status_code == 403
    assert (
        await api.request("viewer-fsi", "GET", f"/api/attachments/{file['id']}/download")
    ).status_code == 404
    listed = (await api.request("viewer-fsi", "GET", f"/api/events/{eid}/attachments")).json()
    assert listed == []
    for user in ("organizer-fsi", "submitter-fsi", "editor", "stupa"):
        assert (await api.request(user, "GET", f"/api/events/{eid}/quotes")).status_code == 200, (
            user
        )


async def test_quote_amounts_do_not_leak(api: Api) -> None:
    eid = await draft_event(api)
    marker = 1_234_567
    quote = (await add_quote(api, eid, amountCents=marker, note="Notiz")).json()
    assert (
        await api.request("organizer-fsi", "POST", f"/api/quotes/{quote['id']}/select")
    ).status_code == 200
    needle = str(marker)
    for path in (
        f"/api/events/{eid}",
        f"/api/events/{eid}/revisions",
        f"/api/events/{eid}/attachments",
        f"/api/events/{eid}/dossier-counts",
        "/api/events?limit=50",
        "/api/public/feed/events",
    ):
        response = await api.request("editor", "GET", path)
        assert needle not in response.text, path
    audit = await api.sql("SELECT data FROM audit_entry")
    assert needle not in json.dumps([str(r[0]) for r in audit])
    revisions = await api.sql("SELECT snapshot FROM event_revision")
    assert needle not in json.dumps([str(r[0]) for r in revisions])
