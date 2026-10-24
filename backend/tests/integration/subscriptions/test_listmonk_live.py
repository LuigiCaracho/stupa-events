"""The whole Listmonk chain against the local dev instance and Mailpit (opt-in: `-m "integration and listmonk"`).

It pins what the contract assumed: a sign-up through our outbox sends no Listmonk opt-in mail
(E16), a digest starts as a draft and sends only after the release, the campaign mail carries
`List-Unsubscribe` with one-click, the one-click unsubscribe is picked up by the reconcile, and
erasing a subscriber removes the Listmonk record.
"""

from __future__ import annotations

import time
import uuid
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import text

from app.modules.subscriptions import digest as digest_module
from app.modules.subscriptions.digest import build_drafts
from app.modules.subscriptions.digest_release import release_digest
from app.modules.subscriptions.digest_template import DigestEvent
from app.modules.subscriptions.outbox import run_outbox
from app.modules.subscriptions.privacy import erase_subscriber
from app.modules.subscriptions.reconcile import reconcile
from tests._support.real_listmonk import MAILPIT, make_real
from tests.integration.subscriptions.listmonk_support import (
    KEY,
    NOW,
    add_subscriber,
    enqueue,
    one,
    scalar,
)

pytest_plugins = ["tests.integration.subscriptions.listmonk_support"]
pytestmark = [pytest.mark.integration, pytest.mark.listmonk]


def mails_to(address: str, wait: float = 0) -> list[dict]:
    try:
        deadline = time.monotonic() + wait
        while True:
            found = httpx.get(f"{MAILPIT}/api/v1/search", params={"query": f"to:{address}"}).json()
            if found["messages"] or time.monotonic() >= deadline:
                return found["messages"]
            time.sleep(0.5)
    except httpx.HTTPError:
        pytest.skip("no Mailpit")


@pytest.fixture
def real():
    harness, _client = make_real()
    yield harness
    harness.cleanup()


async def test_sign_up_digest_release_unsubscribe_and_erase(maker, real, monkeypatch) -> None:  # noqa: ANN001, F811
    category = "zz" + uuid.uuid4().hex[:6]
    async with maker.begin() as session:
        await session.execute(
            text("INSERT INTO category (slug, name, kind) VALUES (:s, 'Live Test', 'format')"),
            {"s": category},
        )
    try:
        await chain(maker, real, monkeypatch, category)
    finally:
        async with maker.begin() as session:
            await session.execute(text("DELETE FROM category WHERE slug = :s"), {"s": category})


async def chain(maker, real, monkeypatch, category: str) -> None:  # noqa: ANN001
    address = f"live-{uuid.uuid4().hex[:8]}@example.test"
    sid = await add_subscriber(maker, address, categories=[category])
    await enqueue(maker, "upsert", sid)
    stats = await run_outbox(maker, real.port, KEY, now=NOW)
    assert stats.done == 1 and stats.failed == 0
    remote = await real.port.find_subscriber(address)
    assert remote is not None
    real.made["subscribers"].append(remote.id)
    list_id = await scalar(
        maker, "SELECT listmonk_id FROM listmonk_list WHERE key = :k", k=category
    )
    real.made["lists"].append(list_id)
    assert list_id in remote.lists and set(remote.lists.values()) == {"confirmed"}
    assert mails_to(address, wait=2) == []

    found = digest_module.WeekEvent(
        DigestEvent("live", "{{ .Subscriber.Email }}", NOW, False, None, None),
        frozenset({category}),
    )

    async def fixed(maker, week_start):  # noqa: ANN001, ANN202
        return [found]

    monkeypatch.setattr(digest_module, "week_events", fixed)
    counters = await build_drafts(maker, real.port, base_url="https://events.example.test", now=NOW)
    assert counters["drafts"] >= 1
    row = await one(maker, "SELECT id, campaign_id FROM digest_run WHERE list_key = :k", k=category)
    real.made["campaigns"].append(row.campaign_id)
    assert await real.port.campaign_status(row.campaign_id) == "draft"
    assert mails_to(address, wait=2) == []

    await release_digest(maker, real.port, row.id, by_sub="sub-editor", now=NOW)
    sent = mails_to(address, wait=30)
    assert sent, "the released campaign did not reach Mailpit (is Listmonk SMTP seeded?)"
    mail = httpx.get(f"{MAILPIT}/api/v1/message/{sent[0]['ID']}").json()
    headers = httpx.get(f"{MAILPIT}/api/v1/message/{sent[0]['ID']}/headers").json()
    assert address not in mail["HTML"]
    assert "List-Unsubscribe" in headers
    assert headers["List-Unsubscribe-Post"] == ["List-Unsubscribe=One-Click"]

    link = headers["List-Unsubscribe"][0].strip("<>")
    assert httpx.post(link, data={"List-Unsubscribe": "One-Click"}).status_code == 200
    report = await reconcile(maker, real.port, KEY, now=NOW)
    assert report.categories_dropped == 1
    assert await scalar(maker, "SELECT categories FROM subscription_profile") == []
    assert await scalar(maker, "SELECT status FROM subscriber") == "confirmed"

    assert await erase_subscriber(maker, maker, sid, by="sub-admin")
    await run_outbox(maker, real.port, KEY, now=NOW + timedelta(days=1))
    assert await real.port.find_subscriber(address) is None
