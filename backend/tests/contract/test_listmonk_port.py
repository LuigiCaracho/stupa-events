"""Port contract: the same checks run against `FakeListmonk` and the real local Listmonk.

The real variant (marker `listmonk`, opt-in) logs into the dev instance as admin, creates a
throwaway API user and removes everything it made. It pins the behaviour the client and the
fake rely on: no PATCH, `unsubscribed` survives an upsert, blocklist is final, campaigns start
as draft, a missing subscriber deletes cleanly.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from app.modules.subscriptions.listmonk_port import CampaignDraft
from tests._support.fake_listmonk import FakeListmonk
from tests._support.real_listmonk import Harness, make_real


@pytest_asyncio.fixture(params=["fake", pytest.param("real", marks=pytest.mark.listmonk)])
async def harness(request: pytest.FixtureRequest) -> AsyncIterator[Harness]:
    if request.param == "fake":
        fake = FakeListmonk()
        yield Harness(
            fake,
            lambda email, list_id: fake.user_unsubscribes(email, list_id),
            lambda: None,
        )
        return
    real, client = make_real()
    yield real
    real.cleanup()
    await client.aclose()


def unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


async def make_list(h: Harness, name: str | None = None) -> int:
    name = name or unique("events-contract")
    list_id = await h.port.ensure_list("k", name)
    h.made["lists"].append(list_id)
    return list_id


def email() -> str:
    return f"{unique('c')}@example.test"


async def test_ensure_list_is_idempotent(harness: Harness) -> None:
    name = unique("events-contract")
    first = await harness.port.ensure_list("k", name)
    assert await harness.port.ensure_list("k", name) == first
    harness.made["lists"].append(first)


async def test_upsert_creates_a_confirmed_subscriber_on_the_lists(harness: Harness) -> None:
    a, b = await make_list(harness), await make_list(harness)
    address = email()
    created = await harness.port.upsert_subscriber(address, {a, b}, {"source": "get-started"})
    harness.made["subscribers"].append(created.id)
    assert created.lists == {a: "confirmed", b: "confirmed"}
    assert (await harness.port.find_subscriber(address)).id == created.id  # type: ignore[union-attr]
    assert await harness.port.find_subscriber(email()) is None


async def test_upsert_adds_and_removes_lists_and_merges_attributes(harness: Harness) -> None:
    a, b, c = [await make_list(harness) for _ in range(3)]
    address = email()
    first = await harness.port.upsert_subscriber(address, {a, b}, {"source": "get-started", "v": 1})
    harness.made["subscribers"].append(first.id)
    second = await harness.port.upsert_subscriber(address, {b, c}, {"v": 2})
    assert second.lists == {b: "confirmed", c: "confirmed"}
    assert second.attribs == {"source": "get-started", "v": 2}


async def test_unsubscribed_list_survives_an_upsert(harness: Harness) -> None:
    a, b = await make_list(harness), await make_list(harness)
    address = email()
    first = await harness.port.upsert_subscriber(address, {a, b}, {})
    harness.made["subscribers"].append(first.id)
    harness.unsubscribe(address, a)
    after = await harness.port.upsert_subscriber(address, {a, b}, {"v": 3})
    assert after.lists[a] == "unsubscribed"
    assert after.lists[b] == "confirmed"


async def test_blocklist_is_final_and_delete_is_idempotent(harness: Harness) -> None:
    a = await make_list(harness)
    address = email()
    sub = await harness.port.upsert_subscriber(address, {a}, {})
    await harness.port.blocklist(sub.id)
    blocked = await harness.port.find_subscriber(address)
    assert blocked is not None and blocked.status == "blocklisted"
    again = await harness.port.upsert_subscriber(address, {a}, {})
    assert again.status == "blocklisted"
    await harness.port.delete_subscriber(sub.id)
    assert await harness.port.find_subscriber(address) is None
    await harness.port.delete_subscriber(sub.id)


async def test_resubscribe_lifts_the_block_and_confirms_the_lists(harness: Harness) -> None:
    a, b = await make_list(harness), await make_list(harness)
    address = email()
    sub = await harness.port.upsert_subscriber(address, {a, b}, {})
    harness.made["subscribers"].append(sub.id)
    await harness.port.blocklist(sub.id)
    blocked = await harness.port.find_subscriber(address)
    assert blocked is not None
    await harness.port.resubscribe(blocked, {a, b})
    back = await harness.port.find_subscriber(address)
    assert back is not None and back.status == "enabled"
    assert back.lists == {a: "confirmed", b: "confirmed"}


async def test_list_states_and_count(harness: Harness) -> None:
    a = await make_list(harness)
    addresses = [email(), email()]
    for address in addresses:
        sub = await harness.port.upsert_subscriber(address, {a}, {})
        harness.made["subscribers"].append(sub.id)
    seen = {s.email async for s in harness.port.list_states({a})}
    assert seen == set(addresses)
    assert await harness.port.subscriber_count(a) == 2


async def test_campaign_starts_as_draft_and_is_found_by_name(harness: Harness) -> None:
    a = await make_list(harness)
    name = unique("events-digest-contract")
    assert await harness.port.find_campaign(name) is None
    campaign = await harness.port.create_campaign(
        CampaignDraft(name, "Betreff", (a,), "<p>Hallo</p>")
    )
    harness.made["campaigns"].append(campaign)
    assert await harness.port.campaign_status(campaign) == "draft"
    assert await harness.port.find_campaign(name) == campaign
    await harness.port.start_campaign(campaign)
    assert await harness.port.campaign_status(campaign) != "draft"


async def test_list_can_be_archived(harness: Harness) -> None:
    a = await make_list(harness)
    await harness.port.archive_list(a)
