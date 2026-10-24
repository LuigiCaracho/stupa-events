"""Digest release route and status counters: rights, the count guard, the counters."""

from __future__ import annotations

import pytest

from app.modules.subscriptions.db import get_subs_maker
from app.modules.subscriptions.digest_admin_router import listmonk_port
from app.modules.subscriptions.listmonk_port import CampaignDraft
from tests._support.fake_listmonk import FakeListmonk
from tests.integration.subscriptions.subs_harness import (
    SubsApi,
    api,
    clean_events,
    db_roles,
    subs,
    subs_url,
)

__fixtures__ = (api, clean_events, db_roles, subs, subs_url)
pytestmark = pytest.mark.integration
DIGESTS = "/api/admin/digests"
STATUS = "/api/admin/subscriptions/status"


async def wire(subs: SubsApi) -> FakeListmonk:
    """Point the routes at the test role and a fake Listmonk with one list and one draft."""
    fake = FakeListmonk()
    overrides = subs.api.app.dependency_overrides
    overrides[get_subs_maker] = lambda: subs.maker
    overrides[listmonk_port] = lambda: fake
    list_id = await fake.ensure_list("_all", "events-alle")
    await subs.sql(
        "INSERT INTO listmonk_list (key, listmonk_id, name) VALUES ('_all', :i, 'events-alle')",
        i=list_id,
    )
    campaign = await fake.create_campaign(CampaignDraft("d", "s", (list_id,), "b"))
    await subs.sql(
        "INSERT INTO digest_run (week_start, list_key, campaign_id, status, event_count) "
        "VALUES ('2026-10-26', '_all', :c, 'draft', 3)",
        c=campaign,
    )
    return fake


async def run_id(subs: SubsApi) -> str:
    return str(await subs.scalar("SELECT id FROM digest_run"))


async def test_only_editors_and_admins_see_and_release(subs: SubsApi) -> None:
    await wire(subs)
    rid = await run_id(subs)
    assert (await subs.api.request(None, "GET", DIGESTS)).status_code == 401
    for user in ("member", "organizer-fsi"):
        assert (await subs.api.request(user, "GET", DIGESTS)).status_code == 403, user
        released = await subs.api.request(user, "POST", f"{DIGESTS}/{rid}/release")
        assert released.status_code == 403, user
        assert (await subs.api.request(user, "GET", STATUS)).status_code == 403, user
    listed = await subs.api.request("editor", "GET", DIGESTS)
    assert listed.status_code == 200
    assert [(r["listKey"], r["status"], r["eventCount"]) for r in listed.json()] == [
        ("_all", "draft", 3)
    ]


async def test_release_waits_for_matching_counts_then_starts_the_campaign(subs: SubsApi) -> None:
    fake = await wire(subs)
    rid = await run_id(subs)
    await subs.register("ada@example.org")
    blocked = await subs.api.request("editor", "POST", f"{DIGESTS}/{rid}/release")
    assert blocked.status_code == 409 and blocked.json()["code"] == "count_mismatch"
    await fake.upsert_subscriber("ada@example.org", set(fake.lists), {})
    done = await subs.api.request("editor", "POST", f"{DIGESTS}/{rid}/release")
    assert done.status_code == 204
    assert {c["status"] for c in fake.campaigns.values()} == {"running"}
    assert await subs.scalar("SELECT status FROM digest_run") == "released"
    again = await subs.api.request("editor", "POST", f"{DIGESTS}/{rid}/release")
    assert again.status_code == 409 and again.json()["code"] == "not_draft"


async def test_status_counts_the_backlog_without_addresses(subs: SubsApi) -> None:
    await wire(subs)
    await subs.register("ada@example.org")
    response = await subs.api.request("editor", "GET", STATUS)
    assert response.status_code == 200
    body = response.json()
    assert body["outboxPending"] == 1 and body["outboxDead"] == 0
    assert body["outboxLagSeconds"] >= 0 and body["breakerOpen"] is False
    assert "ada" not in response.text
