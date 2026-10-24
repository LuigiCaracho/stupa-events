"""Retention jobs and erasure: only `privacy_*` functions remove personal data."""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import text

from app.modules.subscriptions.outbox import run_outbox
from app.modules.subscriptions.privacy import erase_subscriber, purge_expired
from tests.integration.subscriptions.listmonk_support import (
    KEY,
    NOW,
    add_subscriber,
    enqueue,
    one,
    scalar,
)

pytest_plugins = ["tests.integration.subscriptions.listmonk_support"]
pytestmark = pytest.mark.integration


async def audits(maker) -> list[tuple[str, dict]]:  # noqa: ANN001
    async with maker() as session:
        rows = await session.execute(text("SELECT action, data FROM audit_entry ORDER BY id"))
        return [(r.action, r.data) for r in rows]


async def test_pending_older_than_48_hours_is_gone_younger_stays(maker) -> None:  # noqa: ANN001
    await add_subscriber(
        maker, "old@example.test", status="pending", created_at=NOW - timedelta(hours=49)
    )
    await add_subscriber(
        maker, "new@example.test", status="pending", created_at=NOW - timedelta(hours=47)
    )
    counts = await purge_expired(maker, maker, now=NOW)
    assert counts["pending"] == 1
    assert await scalar(maker, "SELECT count(*) FROM subscriber") == 1
    kept = await one(
        maker,
        "SELECT count(*) FILTER (WHERE mail_enabled) AS on_, count(*) FILTER (WHERE subscriber_id IS NULL) AS free FROM subscription_profile",
    )
    assert (kept.on_, kept.free) == (1, 1)


async def test_unsubscribed_after_30_days_become_a_tombstone_without_personal_data(maker) -> None:  # noqa: ANN001
    sid = await add_subscriber(
        maker, "gone@example.test", status="unsubscribed", unsubscribed_at=NOW - timedelta(days=31)
    )
    await add_subscriber(
        maker,
        "recent@example.test",
        status="unsubscribed",
        unsubscribed_at=NOW - timedelta(days=29),
    )
    counts = await purge_expired(maker, maker, now=NOW)
    assert counts["unsubscribed"] == 1
    row = await one(maker, "SELECT * FROM subscriber WHERE id = :i", i=sid)
    assert row.status == "erased"
    assert row.email_enc is None and row.email_hmac is None
    assert row.confirm_token_hash is None and row.manage_token_hash is None
    assert list(row.consent_categories) == [] and row.listmonk_subscriber_id is None
    assert (
        await scalar(
            maker, "SELECT count(*) FROM subscription_profile WHERE subscriber_id = :i", i=sid
        )
        == 0
    )
    assert await scalar(maker, "SELECT count(*) FROM subscriber WHERE status = 'unsubscribed'") == 1


async def test_calendar_profiles_expire_12_months_after_the_last_fetch(maker) -> None:  # noqa: ANN001
    for token, fetched in (
        ("stale", NOW - timedelta(days=400)),
        ("fresh", NOW - timedelta(days=10)),
    ):
        async with maker.begin() as session:
            await session.execute(
                text(
                    "INSERT INTO subscription_profile (questionnaire_version, interests, categories, "
                    "ics_token_hash, last_fetched_on) VALUES (1, '[]', '{party}', :t, :d)"
                ),
                {"t": token, "d": fetched.date()},
            )
    await add_subscriber(maker, "mail@example.test", mail=True)
    async with maker.begin() as session:
        await session.execute(
            text(
                "UPDATE subscription_profile SET created_at = now() - interval '2 years' WHERE subscriber_id IS NOT NULL"
            )
        )
    counts = await purge_expired(maker, maker, now=NOW)
    assert counts["profiles"] == 1
    assert (
        await scalar(
            maker, "SELECT count(*) FROM subscription_profile WHERE ics_token_hash = 'stale'"
        )
        == 0
    )
    assert await scalar(maker, "SELECT count(*) FROM subscription_profile") == 2


async def test_finished_outbox_rows_go_after_30_days(maker) -> None:  # noqa: ANN001
    await enqueue(maker, "upsert", None)
    async with maker.begin() as session:
        await session.execute(
            text("UPDATE outbox SET state = 'done', done_at = :t"), {"t": NOW - timedelta(days=31)}
        )
    await enqueue(maker, "upsert", None)
    assert (await purge_expired(maker, maker, now=NOW))["outbox"] == 1
    assert await scalar(maker, "SELECT count(*) FROM outbox") == 1


async def test_purge_audits_counts_only(maker) -> None:  # noqa: ANN001
    await add_subscriber(
        maker, "old@example.test", status="pending", created_at=NOW - timedelta(hours=60)
    )
    await purge_expired(maker, maker, now=NOW)
    entries = await audits(maker)
    assert entries == [("privacy.purge_pending", {"count": 1, "by": "system"})]
    await purge_expired(maker, maker, now=NOW)
    assert len(await audits(maker)) == 1


async def test_erase_removes_address_profile_tokens_and_the_listmonk_record(maker, fake) -> None:  # noqa: ANN001
    sid = await add_subscriber(maker, "a@example.test")
    await enqueue(maker, "upsert", sid)
    await run_outbox(maker, fake, KEY, now=NOW)
    assert await erase_subscriber(maker, maker, sid, by="sub-admin")
    await run_outbox(maker, fake, KEY, now=NOW + timedelta(days=1))
    assert fake.subscribers == {}
    assert await scalar(maker, "SELECT count(*) FROM subscription_profile") == 0
    assert await scalar(
        maker,
        "SELECT email_enc IS NULL AND email_hmac IS NULL FROM subscriber WHERE id = :i",
        i=sid,
    )
    assert not await erase_subscriber(maker, maker, sid, by="sub-admin")
    assert await audits(maker) == [
        ("subscriber.erase", {"found": True, "by": "sub-admin"}),
        ("subscriber.erase", {"found": False, "by": "sub-admin"}),
    ]
