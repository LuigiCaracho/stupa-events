"""The worker `advance_states` against a real Postgres on a fixed clock (contract 6)."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pytest

import worker.advance as advance_module
from tests.integration.events.harness import Api, future
from worker.advance import advance_one, advance_states

pytestmark = pytest.mark.integration


async def run(api: Api, now: datetime) -> str:
    return await advance_states({"advance_sessionmaker": api.maker, "redis": api.pool}, now=now)


async def scheduled(api: Api, *, poster: bool = False, **over: object) -> tuple[dict, datetime]:
    """An `approved` dossier with `publish_at` one day before the start."""
    event = await api.create_event(**over)
    eid = event["id"]
    await api.fire("organizer-fsi", eid, "T01")
    if poster:
        up = await api.upload_poster("organizer-fsi", eid)
        assert await api.process_poster(up.json()["id"]) == "clean"
    else:
        await api.action("editor", eid, "image-exception", reason="Test ohne Motiv")
    await api.fire("organizer-fsi", eid, "T02")
    when = datetime.fromisoformat(event["startsAt"]) - timedelta(days=1)
    approved = await api.fire("editor", eid, "T04", publishAt=when.isoformat())
    assert approved.status_code == 200, approved.text
    return approved.json(), when


async def state_of(api: Api, eid: str) -> str:
    return (await api.sql("SELECT state FROM event WHERE id = :i", i=eid))[0][0]


async def test_a_due_publish_at_goes_live_once(api: Api) -> None:
    event, when = await scheduled(api)
    assert (await run(api, when - timedelta(minutes=1))).startswith("published=0")
    assert await state_of(api, event["id"]) == "approved"
    assert (await run(api, when)).startswith("published=1")
    assert await state_of(api, event["id"]) == "live"
    assert (await run(api, when + timedelta(minutes=15))).startswith("published=0")
    assert api.pool.counters.get("events:feed:version", 0) >= 1
    feed = (await api.request(None, "GET", "/api/public/feed/events")).json()
    assert [i["id"] for i in feed["items"]] == [event["id"]]
    row = await api.sql(
        "SELECT actor_type, actor_id FROM event_status_event WHERE transition_id = 'T05'"
    )
    assert row == [("system", "system:advance_states")]


async def test_without_publish_at_the_worker_waits_for_a_person(api: Api) -> None:
    event = await api.to_state("approved")
    assert (await run(api, future(30))).startswith("published=0")
    assert await state_of(api, event["id"]) == "approved"


async def test_a_poster_that_turned_invalid_blocks_the_worker(
    api: Api, caplog: pytest.LogCaptureFixture
) -> None:
    event, when = await scheduled(api, poster=True)
    await api.sql("ALTER TABLE attachment DISABLE TRIGGER trg_attachment_keep_published_poster")
    await api.sql("UPDATE attachment SET scan_status = 'error' WHERE event_id = :i", i=event["id"])
    with caplog.at_level(logging.WARNING, logger="worker.advance"):
        summary = await run(api, when)
    await api.sql("ALTER TABLE attachment ENABLE TRIGGER trg_attachment_keep_published_poster")
    assert "blocked=1" in summary and "published=0" in summary
    assert f"advance_blocked event={event['id']} code=image_required" in caplog.text
    assert await state_of(api, event["id"]) == "approved"


async def test_the_worker_never_publishes_without_a_human_approval(api: Api) -> None:
    event, when = await scheduled(api)
    for approver in ("system:import", "system:advance_states"):
        await api.sql("UPDATE event SET approved_by = :a WHERE id = :i", a=approver, i=event["id"])
        assert "blocked=1" in await run(api, when)
        assert await state_of(api, event["id"]) == "approved"


async def test_a_missed_date_is_not_published_late(api: Api) -> None:
    event, when = await scheduled(api)
    ends = datetime.fromisoformat(event["endsAt"])
    assert "blocked=1" in await run(api, ends + timedelta(hours=1))
    assert await state_of(api, event["id"]) == "approved"


@pytest.mark.parametrize(
    ("origin", "target", "key"),
    [("internal", "followup", "followup=1"), ("imported", "archived", "archived=1")],
)
async def test_live_events_leave_twelve_hours_after_the_end(
    api: Api, origin: str, target: str, key: str
) -> None:
    event = await api.to_state("live")
    await api.sql("UPDATE event SET origin_kind = :o WHERE id = :i", o=origin, i=event["id"])
    ends = datetime.fromisoformat(event["endsAt"])
    assert "followup=0 archived=0" in await run(api, ends + timedelta(hours=11, minutes=59))
    assert key in await run(api, ends + timedelta(hours=12))
    assert await state_of(api, event["id"]) == target


@pytest.mark.parametrize(("days", "archived"), [(29, 0), (30, 1)])
async def test_followup_is_archived_after_thirty_days(api: Api, days: int, archived: int) -> None:
    event = await api.to_state("live")
    eid = event["id"]
    entered = datetime.fromisoformat(event["endsAt"]) + timedelta(days=1)
    await api.sql("UPDATE event SET state = 'followup' WHERE id = :i", i=eid)
    await api.sql(
        "INSERT INTO event_status_event (event_id, to_state, transition_id, actor_type, at) "
        "VALUES (:i, 'followup', 'T08', 'system', :at)",
        i=eid,
        at=entered,
    )
    summary = await run(api, entered + timedelta(days=days))
    assert f"archived={archived}" in summary
    assert await state_of(api, eid) == ("archived" if archived else "followup")


async def test_a_person_who_was_faster_wins(api: Api) -> None:
    event, when = await scheduled(api)
    assert (await api.fire("editor", event["id"], "T05")).status_code == 200
    outcome = await advance_one(api.maker, api.pool, event["id"], "T05", when)
    assert outcome == "skipped"


async def test_one_broken_dossier_does_not_stop_the_run(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, when = await scheduled(api, title="Eins")
    second, _ = await scheduled(api, title="Zwei")
    real = advance_module.advance_one
    calls: list[str] = []

    async def flaky(maker, pool, event_id, transition, now):  # noqa: ANN001, ANN202
        calls.append(str(event_id))
        if len(calls) == 1:
            raise RuntimeError("boom")
        return await real(maker, pool, event_id, transition, now)

    monkeypatch.setattr(advance_module, "advance_one", flaky)
    summary = await run(api, when + timedelta(hours=1))
    assert "published=1" in summary and "failed=1" in summary
    states = {await state_of(api, first["id"]), await state_of(api, second["id"])}
    assert states == {"live", "approved"}


async def test_the_default_sessionmaker_is_the_fallback(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(advance_module, "get_sessionmaker", lambda: api.maker)
    assert await advance_states({}, now=future(1)) == (
        "published=0 followup=0 archived=0 blocked=0 skipped=0 failed=0"
    )


async def test_blocked_dossiers_never_starve_a_due_one(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(advance_module, "BATCH", 2)
    blocked = [(await scheduled(api, poster=True))[0] for _ in range(3)]
    good, when = await scheduled(api)
    await api.sql("ALTER TABLE attachment DISABLE TRIGGER trg_attachment_keep_published_poster")
    for event in blocked:
        await api.sql(
            "UPDATE attachment SET scan_status = 'error' WHERE event_id = :i", i=event["id"]
        )
        await api.sql(
            "UPDATE event SET publish_at = :p WHERE id = :i",
            p=when - timedelta(days=5),
            i=event["id"],
        )
    summary = await run(api, when)
    await api.sql("ALTER TABLE attachment ENABLE TRIGGER trg_attachment_keep_published_poster")
    assert "published=1" in summary and "blocked=3" in summary
    assert await state_of(api, good["id"]) == "live"
