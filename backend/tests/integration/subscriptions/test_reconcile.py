"""Daily reconcile: our record wins, an opt-out inside Listmonk is final."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from app.modules.subscriptions.listmonk_sync import ALL_KEY
from app.modules.subscriptions.outbox import run_outbox
from app.modules.subscriptions.reconcile import reconcile
from tests.integration.subscriptions.listmonk_support import (
    KEY,
    NOW,
    add_subscriber,
    enqueue,
    scalar,
)

pytest_plugins = ["tests.integration.subscriptions.listmonk_support"]
pytestmark = pytest.mark.integration


async def settled(maker, fake, *addresses: str, categories=("party", "kino")):  # noqa: ANN001, ANN201
    ids = {}
    for address in addresses:
        ids[address] = await add_subscriber(maker, address, categories=list(categories))
        await enqueue(maker, "upsert", ids[address])
    await run_outbox(maker, fake, KEY, now=NOW)
    return ids


def list_id(fake, key: str) -> int:  # noqa: ANN001
    return next(i for i, n in fake.lists.items() if n == f"events-{key}")


async def test_unsubscribe_link_is_taken_over_and_stays_after_the_next_sync(maker, fake) -> None:  # noqa: ANN001
    ids = await settled(maker, fake, "a@example.test")
    fake.user_blocklists("a@example.test")
    report = await reconcile(maker, fake, KEY, now=NOW)
    assert report.unsubscribed == 1
    assert await scalar(maker, "SELECT status FROM subscriber") == "unsubscribed"
    assert await scalar(maker, "SELECT mail_enabled FROM subscription_profile") is False
    await enqueue(maker, "upsert", ids["a@example.test"])
    await run_outbox(maker, fake, KEY, now=NOW)
    again = await reconcile(maker, fake, KEY, now=NOW)
    assert again.unsubscribed == 0
    assert await scalar(maker, "SELECT status FROM subscriber") == "unsubscribed"
    assert fake.by_email("a@example.test").status == "blocklisted"  # type: ignore[union-attr]


async def test_leaving_every_list_is_an_unsubscribe(maker, fake) -> None:  # noqa: ANN001
    await settled(maker, fake, "a@example.test")
    for key in (ALL_KEY, "party", "kino"):
        name_id = next(
            i
            for i, n in fake.lists.items()
            if n == ("events-alle" if key == ALL_KEY else f"events-{key}")
        )
        fake.user_unsubscribes("a@example.test", name_id)
    await reconcile(maker, fake, KEY, now=NOW)
    assert await scalar(maker, "SELECT status FROM subscriber") == "unsubscribed"


async def test_leaving_one_category_list_drops_the_category(maker, fake) -> None:  # noqa: ANN001
    await settled(maker, fake, "a@example.test")
    fake.user_unsubscribes("a@example.test", list_id(fake, "kino"))
    report = await reconcile(maker, fake, KEY, now=NOW)
    assert report.categories_dropped == 1
    assert await scalar(maker, "SELECT categories FROM subscription_profile") == ["party"]
    assert await scalar(maker, "SELECT status FROM subscriber") == "confirmed"


async def test_stranger_on_an_events_list_is_removed_from_the_lists_not_deleted(
    maker, fake
) -> None:  # noqa: ANN001
    await settled(maker, fake, "a@example.test")
    foreign = fake.add_foreign("stranger@example.test", list_id(fake, "party"))
    report = await reconcile(maker, fake, KEY, now=NOW)
    assert report.foreign_on_lists == 1
    remaining = fake.subscribers[foreign.id]
    assert remaining.lists == {}


async def test_pending_address_on_a_list_counts_as_a_stranger(maker, fake) -> None:  # noqa: ANN001
    await settled(maker, fake, "a@example.test")
    await add_subscriber(maker, "p@example.test", status="pending")
    fake.add_foreign("p@example.test", list_id(fake, "party"))
    assert (await reconcile(maker, fake, KEY, now=NOW)).foreign_on_lists == 1


async def test_confirmed_subscriber_missing_in_listmonk_is_queued_again(maker, fake) -> None:  # noqa: ANN001
    ids = await settled(maker, fake, "a@example.test")
    fake.subscribers.clear()
    report = await reconcile(maker, fake, KEY, now=NOW)
    assert report.requeued == 1
    assert (
        await scalar(maker, "SELECT count(*) FROM outbox WHERE idempotency_key LIKE '%reconcile%'")
        == 1
    )
    await reconcile(maker, fake, KEY, now=NOW)
    assert (
        await scalar(maker, "SELECT count(*) FROM outbox WHERE idempotency_key LIKE '%reconcile%'")
        == 1
    )
    await run_outbox(maker, fake, KEY, now=NOW + timedelta(days=1))
    assert fake.by_email("a@example.test") is not None
    assert ids


async def test_list_missing_on_the_subscriber_is_queued_again(maker, fake) -> None:  # noqa: ANN001
    await settled(maker, fake, "a@example.test")
    remote = fake.by_email("a@example.test")
    fake.subscribers[remote.id] = remote.__class__(  # type: ignore[union-attr]
        remote.id,
        remote.email,
        remote.status,
        {list_id(fake, "party"): "confirmed"},
        remote.attribs,
    )
    assert (await reconcile(maker, fake, KEY, now=NOW)).requeued == 1


async def test_category_lists_follow_the_active_categories(maker, fake) -> None:  # noqa: ANN001
    await reconcile(maker, fake, KEY, now=NOW)
    names = set(fake.lists.values())
    assert "events-alle" in names and "events-party" in names
    async with maker.begin() as session:
        await session.execute(text("UPDATE category SET active = false WHERE slug = 'party'"))
    try:
        await reconcile(maker, fake, KEY, now=NOW)
        assert await scalar(
            maker, "SELECT archived_at IS NOT NULL FROM listmonk_list WHERE key = 'party'"
        )
        assert list_id(fake, "party") in fake.archived
    finally:
        async with maker.begin() as session:
            await session.execute(text("UPDATE category SET active = true WHERE slug = 'party'"))
