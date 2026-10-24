"""Outbox runner against a real database and the fake Listmonk."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.modules.subscriptions.listmonk_port import ListmonkError
from app.modules.subscriptions.outbox import BREAKER_KEY, run_outbox
from tests._support.fake_listmonk import FakeListmonk
from tests.integration.subscriptions.listmonk_support import (
    KEY,
    NOW,
    Maker,
    MemoryBreaker,
    add_subscriber,
    enqueue,
    one,
    scalar,
)

pytest_plugins = ["tests.integration.subscriptions.listmonk_support"]
pytestmark = pytest.mark.integration


async def run(maker: Maker, fake: FakeListmonk, **kw: object):  # noqa: ANN201, F811
    return await run_outbox(maker, fake, KEY, now=kw.pop("now", NOW), **kw)  # type: ignore[arg-type]


async def test_only_parties_gives_the_party_lists_and_no_meeting_list(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test", categories=["party"])
    await enqueue(maker, "upsert", sid)
    stats = await run(maker, fake)
    assert stats.done == 1
    names = {n for n in fake.lists.values()}
    assert names == {"events-alle", "events-party"}
    remote = fake.by_email("a@example.test")
    assert remote is not None and len(remote.lists) == 2
    assert remote.attribs["source"] == "get-started"
    assert remote.attribs["kategorien"] == ["party"]
    assert await scalar(maker, "SELECT listmonk_subscriber_id FROM subscriber") == remote.id
    assert await scalar(maker, "SELECT state FROM outbox") == "done"


async def test_list_registry_is_reused(maker, fake) -> None:  # noqa: ANN001
    for address in ("a@example.test", "b@example.test"):
        await enqueue(maker, "upsert", await add_subscriber(maker, address))
    await run(maker, fake)
    assert fake.calls.count("ensure_list") == 2
    assert await scalar(maker, "SELECT count(*) FROM listmonk_list") == 2


async def test_mail_switched_off_leaves_all_lists(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    async with maker.begin() as session:
        from sqlalchemy import text

        await session.execute(text("UPDATE subscription_profile SET mail_enabled = false"))
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    assert fake.by_email("a@example.test").lists == {}  # type: ignore[union-attr]


async def test_job_for_an_unconfirmed_or_missing_subscriber_does_nothing(maker, fake) -> None:  # noqa: ANN001
    pending = await add_subscriber(maker, "p@example.test", status="pending")
    await enqueue(maker, "upsert", pending)
    await enqueue(maker, "upsert", None)
    stats = await run(maker, fake)
    assert stats.done == 2
    assert fake.subscribers == {}


async def test_listmonk_down_loses_nothing_and_catches_up(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    fake.down = True
    stats = await run(maker, fake)
    assert (stats.done, stats.failed) == (0, 1)
    row = await one(maker, "SELECT state, attempts, next_at, last_error FROM outbox")
    assert (row.state, row.attempts, row.last_error) == ("pending", 1, "ConnectError")
    assert row.next_at == NOW + timedelta(seconds=60)
    assert await scalar(maker, "SELECT status FROM subscriber") == "confirmed"
    fake.down = False
    assert (await run(maker, fake)).done == 0
    later = await run(maker, fake, now=NOW + timedelta(minutes=2))
    assert later.done == 1
    assert fake.by_email("a@example.test") is not None


async def test_failed_try_waits_longer_each_time_and_dies_after_ten(maker, fake) -> None:  # noqa: ANN001
    await enqueue(maker, "upsert", await add_subscriber(maker, "a@example.test"))
    fake.down = True
    moment = NOW
    for attempt in range(1, 11):
        await run(maker, fake, now=moment)
        row = await one(maker, "SELECT state, attempts FROM outbox")
        assert row.attempts == attempt
        moment += timedelta(hours=2)
    assert row.state == "dead"
    assert (await run(maker, fake, now=moment)).failed == 0


async def test_error_that_cannot_improve_dies_after_three_tries(maker, fake) -> None:  # noqa: ANN001
    await enqueue(maker, "upsert", await add_subscriber(maker, "a@example.test"))
    fake.fail_next(9, ListmonkError("http_error", status=400, retryable=False))
    moment = NOW
    for _ in range(3):
        await run(maker, fake, now=moment)
        moment += timedelta(hours=2)
    row = await one(maker, "SELECT state, attempts, last_error FROM outbox")
    assert (row.state, row.attempts, row.last_error) == ("dead", 3, "http_error:400")


async def test_breaker_opens_after_five_failures_and_keeps_the_rest(maker, fake) -> None:  # noqa: ANN001
    for i in range(8):
        await enqueue(maker, "upsert", await add_subscriber(maker, f"u{i}@example.test"))
    fake.down = True
    breaker = MemoryBreaker()
    stats = await run(maker, fake, breaker=breaker)
    assert stats.failed == 5 and stats.breaker_open
    assert BREAKER_KEY in breaker.keys
    assert await scalar(maker, "SELECT count(*) FROM outbox WHERE state = 'pending'") == 8
    assert await scalar(maker, "SELECT count(*) FROM outbox WHERE attempts = 0") == 3
    calls = len(fake.calls)
    again = await run(maker, fake, breaker=breaker, now=NOW + timedelta(hours=3))
    assert again.breaker_open and len(fake.calls) == calls


async def test_same_state_twice_changes_nothing_the_second_time(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    assert fake.calls.count("upsert_subscriber") == 2
    assert len(fake.subscribers) == 1


async def test_an_opt_out_inside_listmonk_wins_over_the_outbox(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    fake.user_blocklists("a@example.test")
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    assert await scalar(maker, "SELECT status FROM subscriber") == "unsubscribed"
    assert await scalar(maker, "SELECT mail_enabled FROM subscription_profile") is False
    assert fake.by_email("a@example.test").status == "blocklisted"  # type: ignore[union-attr]


async def test_a_list_the_person_left_is_not_added_again(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test", categories=["party", "kino"])
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    kino = next(i for i, n in fake.lists.items() if n == "events-kino")
    fake.user_unsubscribes("a@example.test", kino)
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    assert fake.by_email("a@example.test").lists[kino] == "unsubscribed"  # type: ignore[union-attr]
    assert await scalar(maker, "SELECT status FROM subscriber") == "confirmed"


async def test_unsubscribe_job_blocklists_the_subscriber(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    async with maker.begin() as session:
        from sqlalchemy import text

        await session.execute(text("UPDATE subscriber SET status = 'unsubscribed'"))
    await enqueue(maker, "unsubscribe", sid)
    await run(maker, fake)
    assert fake.by_email("a@example.test").status == "blocklisted"  # type: ignore[union-attr]


async def test_delete_job_removes_the_record_and_drops_the_ciphertext(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    await run(maker, fake)
    async with maker.begin() as session:
        from sqlalchemy import text

        await session.execute(text("SELECT privacy_erase_subscriber(:i)"), {"i": sid})
    assert await scalar(maker, "SELECT payload ? 'emailEnc' FROM outbox WHERE op = 'delete'")
    await run(maker, fake, now=NOW + timedelta(days=1))
    assert fake.subscribers == {}
    row = await one(maker, "SELECT state, payload FROM outbox WHERE op = 'delete'")
    assert row.state == "done" and "emailEnc" not in row.payload
    assert row.payload["listmonkSubscriberId"] is not None


async def test_delete_finds_the_record_by_address_when_the_id_was_never_stored(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    fake.add_foreign("a@example.test", 99)
    async with maker.begin() as session:
        from sqlalchemy import text

        await session.execute(text("SELECT privacy_erase_subscriber(:i)"), {"i": sid})
    await run(maker, fake, now=NOW + timedelta(days=1))
    assert fake.subscribers == {}


async def test_orphaned_running_job_is_picked_up_again(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    job = await enqueue(maker, "upsert", sid)
    async with maker.begin() as session:
        from sqlalchemy import text

        await session.execute(
            text("UPDATE outbox SET state = 'running', locked_at = :t WHERE id = :i"),
            {"t": NOW - timedelta(minutes=10), "i": job},
        )
    assert (await run(maker, fake)).done == 1
