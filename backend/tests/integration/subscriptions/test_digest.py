"""Digest drafts: one per list and week, never released by the job, Go-template safe."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import text

from app.modules.subscriptions import digest as digest_module
from app.modules.subscriptions.digest import build_drafts, week_events, week_start_of
from app.modules.subscriptions.digest_release import (
    ReleaseBlockedError,
    mark_released_in_listmonk,
    release_digest,
)
from app.modules.subscriptions.digest_template import DigestEvent
from app.modules.subscriptions.outbox import BREAKER_KEY, run_outbox
from tests.integration.events.harness import Api, api, clean_events, db_roles  # noqa: F401
from tests.integration.publicapi import site_data
from tests.integration.subscriptions.listmonk_support import (
    KEY,
    NOW,
    MemoryBreaker,
    add_subscriber,
    enqueue,
    one,
    scalar,
)

pytest_plugins = ["tests.integration.subscriptions.listmonk_support"]
pytestmark = pytest.mark.integration
MONDAY = datetime(2026, 10, 26, 5, 0, tzinfo=UTC)
WEEK = date(2026, 10, 26)


def week_event(title: str, *categories: str) -> digest_module.WeekEvent:
    event = DigestEvent(
        "e-" + title[:3], title, datetime(2026, 10, 30, 17, tzinfo=UTC), False, "Mensa", None
    )
    return digest_module.WeekEvent(event, frozenset(categories))


@pytest.fixture
def events(monkeypatch: pytest.MonkeyPatch) -> list[digest_module.WeekEvent]:
    found = [week_event("{{ .Subscriber.Email }}", "party"), week_event("Film", "kino")]

    async def fixed(maker, week_start):  # noqa: ANN001, ANN202
        return found

    monkeypatch.setattr(digest_module, "week_events", fixed)
    return found


async def populated(maker, fake) -> None:  # noqa: ANN001
    for address, cats in (("a@example.test", ["party"]), ("b@example.test", ["party", "kino"])):
        await enqueue(maker, "upsert", await add_subscriber(maker, address, categories=cats))
    await run_outbox(maker, fake, KEY, now=NOW)


async def test_week_starts_on_monday_in_berlin() -> None:
    assert week_start_of(datetime(2026, 10, 25, 23, 30, tzinfo=UTC)) == WEEK
    assert week_start_of(datetime(2026, 10, 26, 0, 30, tzinfo=UTC)) == WEEK
    assert week_start_of(datetime(2026, 11, 1, 23, 30, tzinfo=UTC)) == date(2026, 11, 2)


async def test_one_draft_per_list_with_events_and_subscribers(maker, fake, events) -> None:  # noqa: ANN001
    await populated(maker, fake)
    counters = await build_drafts(maker, fake, base_url="https://events.example.test", now=MONDAY)
    assert counters == {"drafts": 3, "skipped": 0}
    rows = await one(
        maker, "SELECT count(*) AS n, bool_and(status = 'draft') AS drafts FROM digest_run"
    )
    assert (rows.n, rows.drafts) == (3, True)
    assert {c["status"] for c in fake.campaigns.values()} == {"draft"}
    names = sorted(c["draft"].name for c in fake.campaigns.values())
    assert names == [f"events-digest-2026-10-26-{k}" for k in ("_all", "kino", "party")]


async def test_a_category_list_shows_only_its_events(maker, fake, events) -> None:  # noqa: ANN001
    await populated(maker, fake)
    await build_drafts(maker, fake, base_url="https://events.example.test", now=MONDAY)
    bodies = {c["draft"].name.rsplit("-", 1)[1]: c["draft"].body for c in fake.campaigns.values()}
    assert "Film" in bodies["kino"] and "&#123;&#123;" not in bodies["kino"]
    assert "Film" not in bodies["party"] and "&#123;&#123; .Subscriber" in bodies["party"]
    assert "Film" in bodies["_all"] and "&#123;&#123; .Subscriber" in bodies["_all"]
    assert all("{{ .Subscriber" not in b for b in bodies.values())
    assert all("{{ UnsubscribeURL }}" in b for b in bodies.values())


async def test_second_run_creates_nothing(maker, fake, events) -> None:  # noqa: ANN001
    await populated(maker, fake)
    await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    again = await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    assert again == {"drafts": 0, "skipped": 0}
    assert len(fake.campaigns) == 3


async def test_crash_between_listmonk_and_database_does_not_duplicate_the_campaign(
    maker, fake, events
) -> None:  # noqa: ANN001
    await populated(maker, fake)
    await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    async with maker.begin() as session:
        await session.execute(text("DELETE FROM digest_run"))
    await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    assert len(fake.campaigns) == 3
    assert await scalar(maker, "SELECT count(*) FROM digest_run") == 3


async def test_list_without_subscribers_is_skipped_and_without_events_ignored(
    maker, fake, events
) -> None:  # noqa: ANN001
    await populated(maker, fake)
    kino = next(i for i, n in fake.lists.items() if n == "events-kino")
    fake.subscribers = {
        i: s
        for i, s in fake.subscribers.items()
        if kino not in s.lists or s.email != "b@example.test"
    }
    events.pop(1)
    counters = await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    assert counters["drafts"] == 2
    assert await scalar(maker, "SELECT count(*) FROM digest_run WHERE list_key = 'kino'") == 0


async def test_release_is_refused_when_counts_differ_and_works_when_they_match(
    maker, fake, events
) -> None:  # noqa: ANN001
    await populated(maker, fake)
    await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    run_id = await scalar(maker, "SELECT id FROM digest_run WHERE list_key = 'party'")
    fake.add_foreign(
        "stranger@example.test", next(i for i, n in fake.lists.items() if n == "events-party")
    )
    with pytest.raises(ReleaseBlockedError) as blocked:
        await release_digest(maker, fake, run_id, by_sub="sub-editor")
    assert blocked.value.code == "count_mismatch"
    assert {c["status"] for c in fake.campaigns.values()} == {"draft"}
    fake.subscribers = {
        i: s for i, s in fake.subscribers.items() if s.email != "stranger@example.test"
    }
    await release_digest(maker, fake, run_id, by_sub="sub-editor", now=MONDAY)
    row = await one(
        maker, "SELECT status, released_by_sub, released_at FROM digest_run WHERE id = :i", i=run_id
    )
    assert (row.status, row.released_by_sub, row.released_at) == ("released", "sub-editor", MONDAY)
    assert [c["status"] for c in fake.campaigns.values()].count("running") == 1


async def test_release_waits_while_the_breaker_is_open_and_only_drafts_release(
    maker, fake, events
) -> None:  # noqa: ANN001
    await populated(maker, fake)
    await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    run_id = await scalar(maker, "SELECT id FROM digest_run WHERE list_key = '_all'")
    breaker = MemoryBreaker()
    breaker.keys[BREAKER_KEY] = "1"
    with pytest.raises(ReleaseBlockedError) as blocked:
        await release_digest(maker, fake, run_id, by_sub="s", breaker=breaker)
    assert blocked.value.code == "listmonk_unavailable"
    breaker.keys.clear()
    await release_digest(maker, fake, run_id, by_sub="s", breaker=breaker)
    with pytest.raises(ReleaseBlockedError) as again:
        await release_digest(maker, fake, run_id, by_sub="s")
    assert again.value.code == "not_draft"


async def test_release_inside_listmonk_is_noticed(maker, fake, events) -> None:  # noqa: ANN001
    await populated(maker, fake)
    await build_drafts(maker, fake, base_url="https://x.test", now=MONDAY)
    campaign = await scalar(maker, "SELECT campaign_id FROM digest_run WHERE list_key = 'kino'")
    fake.campaigns[campaign]["status"] = "running"
    assert await mark_released_in_listmonk(maker, fake) == 1
    assert (
        await scalar(maker, "SELECT status FROM digest_run WHERE list_key = 'kino'") == "released"
    )
    assert await scalar(maker, "SELECT count(*) FROM digest_run WHERE status = 'draft'") == 2


async def test_week_events_reads_scheduled_public_events_of_the_week(api: Api, maker) -> None:  # noqa: ANN001, F811
    site = site_data.Site()
    site_data.configure(api)
    start = datetime(2026, 10, 30, 17, 0, tzinfo=UTC)
    over = {"startsAt": start.isoformat(), "endsAt": start.replace(hour=20).isoformat()}
    await site_data.add(
        api, site, "party", title="Halloween", primaryCategoryId=api.category_ids["party"], **over
    )
    await site_data.add(api, site, "draft", state="draft", title="Entwurf", **over)
    later = {
        "startsAt": datetime(2026, 11, 20, 17, tzinfo=UTC).isoformat(),
        "endsAt": datetime(2026, 11, 20, 19, tzinfo=UTC).isoformat(),
    }
    await site_data.add(api, site, "late", title="Spaeter", **later)
    found = await week_events(maker, WEEK)
    assert [w.event.title for w in found] == ["Halloween"]
    assert found[0].categories == {"party", "campusfest"} or "party" in found[0].categories
    assert found[0].event.starts_at == start
