"""The profile calendar `/ics/p/{token}.ics`: content, headers, equal 404s, rotation, no leaks."""

from __future__ import annotations

import asyncio
import logging
import re
import socket
from pathlib import Path

import httpx
import pytest
import uvicorn
from icalendar import Calendar

from app.shared.ratelimit import InMemoryRateLimiter
from tests.integration.subscriptions.subs_harness import (
    SubsApi,
    api,
    clean_events,
    db_roles,
    link_of,
    subs,
    subs_url,
)

__fixtures__ = (api, clean_events, db_roles, subs, subs_url)
pytestmark = pytest.mark.integration
TOKEN_URL = re.compile(r"/ics/p/([A-Za-z0-9_-]{43})\.ics")
ROOT = Path(__file__).resolve().parents[4]


def summaries(body: bytes) -> list[str]:
    return [str(e["SUMMARY"]) for e in Calendar.from_ical(body).walk("VEVENT")]


async def publish(subs: SubsApi, title: str, category: str) -> dict:
    api = subs.api
    return await api.to_state(
        "published", title=title, primaryCategoryId=api.category_ids[category]
    )


async def profile(subs: SubsApi, **kw: object) -> tuple[str, str]:
    """Create a profile; return its token and the path of its calendar."""
    created = await subs.subscribe(**kw)  # type: ignore[arg-type]
    assert created.status_code == 202
    found = TOKEN_URL.search(created.json()["profile"]["icsUrl"])
    assert found is not None
    return found[1], f"/ics/p/{found[1]}.ics"


async def test_only_parties_and_no_meetings_gives_a_calendar_with_party_events_only(
    subs: SubsApi,
) -> None:
    await publish(subs, "Semesterparty", "party")
    await publish(subs, "Lernwerkstatt", "workshop")
    await publish(subs, "Filmabend", "kino")
    _, path = await profile(subs, interests=("party",))
    response = await subs.api.client.get(path)
    assert response.status_code == 200
    assert summaries(response.content) == ["Semesterparty"]
    assert "X-WR-CALNAME:STUPA Events: Mein Profil" in response.content.decode()
    headers = response.headers
    assert headers["content-type"] == "text/calendar; charset=utf-8"
    assert headers["cache-control"] == "private, max-age=900"
    assert headers["content-disposition"] == 'inline; filename="stupa-events.ics"'
    assert headers["referrer-policy"] == "no-referrer" and headers["x-robots-tag"] == "noindex"
    assert "set-cookie" not in headers and "access-control-allow-origin" not in headers
    again = await subs.api.client.get(path, headers={"If-None-Match": headers["etag"]})
    assert again.status_code == 304 and again.content == b""
    head = await subs.api.client.head(path)
    assert head.status_code == 200


async def test_several_interests_merge_and_sort_without_duplicates(subs: SubsApi) -> None:
    first = await publish(subs, "Erste Party", "party")
    await publish(subs, "Kinoabend", "kino")
    await publish(subs, "Workshop", "workshop")
    _, path = await profile(subs, interests=("party", "kultur"))
    body = (await subs.api.client.get(path)).content
    assert sorted(summaries(body)) == ["Erste Party", "Kinoabend"]
    uids = [str(e["UID"]) for e in Calendar.from_ical(body).walk("VEVENT")]
    assert len(uids) == len(set(uids)) and any(first["id"] in uid for uid in uids)
    assert body.count(b"BEGIN:VTIMEZONE") <= 1


async def test_a_faculty_profile_includes_the_children_of_the_chosen_category(
    subs: SubsApi,
) -> None:
    api = subs.api
    mine = await api.to_state(
        "published",
        title="FSI-Abend",
        primaryCategoryId=api.category_ids["fachschaft-informatik-fsi"],
    )
    await api.to_state(
        "published", title="TEC-Abend", primaryCategoryId=api.category_ids["fachschaft-technik-tec"]
    )
    _, path = await profile(subs, interests=("party",), faculty="fachschaft:informatik-fsi")
    body = (await subs.api.client.get(path)).content
    assert summaries(body) == ["FSI-Abend"] and mine["id"] in body.decode()


async def test_unknown_rotated_revoked_and_malformed_tokens_give_one_identical_404(
    subs: SubsApi,
) -> None:
    created = await subs.subscribe(email="ada@example.org")
    old = TOKEN_URL.search(created.json()["profile"]["icsUrl"])
    assert old is not None
    _, confirm = link_of(subs.queue.sent[-1])
    await subs.confirm(confirm)
    manage = await subs.manage_token("ada@example.org")
    rotated = await subs.api.client.post(
        "/api/public/subscriptions/me/ics-token", headers={"X-Subscription-Token": manage}
    )
    fresh = TOKEN_URL.search(rotated.json()["icsUrl"])
    assert fresh is not None
    assert (await subs.api.client.get(f"/ics/p/{fresh[1]}.ics")).status_code == 200
    assert (await subs.me(manage, "DELETE")).status_code == 204
    paths = [
        f"/ics/p/{old[1]}.ics",
        f"/ics/p/{fresh[1]}.ics",
        f"/ics/p/{'q' * 43}.ics",
        "/ics/p/kurz.ics",
        f"/ics/p/{'q' * 300}.ics",
    ]
    answers = [await subs.api.client.get(p) for p in paths]
    assert {r.status_code for r in answers} == {404}
    assert len({r.content for r in answers}) == 1
    first = answers[0]
    assert first.headers["cache-control"] == "no-store"
    assert first.headers["content-type"].startswith("application/problem+json")
    assert "set-cookie" not in first.headers and first.headers["x-robots-tag"] == "noindex"
    assert first.json()["detail"] == "calendar not found" and "traceId" not in first.json()


async def test_a_fetch_marks_the_day_once_and_never_touches_the_profile_version(
    subs: SubsApi,
) -> None:
    _, path = await profile(subs, interests=("party",))
    before = await subs.sql("SELECT updated_at, last_fetched_on FROM subscription_profile")
    assert before[0].last_fetched_on is None
    await subs.api.client.get(path)
    after = await subs.sql(
        "SELECT updated_at, last_fetched_on, current_date AS today FROM subscription_profile"
    )
    assert (
        after[0].last_fetched_on == after[0].today and after[0].updated_at == before[0].updated_at
    )
    await subs.sql("UPDATE subscription_profile SET last_fetched_on = current_date - 3")
    await subs.api.client.get(path)
    assert await subs.scalar("SELECT last_fetched_on = current_date FROM subscription_profile")


async def test_misses_are_counted_per_ip_and_the_31st_is_a_429(subs: SubsApi) -> None:
    subs.use_limiter(InMemoryRateLimiter())
    codes = [(await subs.api.client.get(f"/ics/p/{'a' * 43}.ics")).status_code for _ in range(31)]
    assert codes[:30] == [404] * 30 and codes[30] == 429


async def test_the_token_never_reaches_a_log_or_the_process_output(
    subs: SubsApi, caplog: pytest.LogCaptureFixture, capfd: pytest.CaptureFixture[str]
) -> None:
    token, path = await profile(subs, interests=("party",))
    with caplog.at_level(logging.DEBUG):
        await subs.api.client.get(path)
        await subs.api.client.get(f"/ics/p/{'z' * 43}.ics")
        server = await _serve(subs)
        try:
            async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{server.port}") as client:
                assert (await client.get(path)).status_code == 200
        finally:
            await server.stop()
    out = capfd.readouterr()
    ours = "\n".join(
        r.getMessage() for r in caplog.records if not r.name.startswith(("httpx", "httpcore"))
    )
    assert token not in ours and token not in out.out + out.err
    assert "z" * 43 not in ours


def test_the_server_start_commands_switch_the_access_log_off() -> None:
    assert "--no-access-log" in (ROOT / "backend" / "Dockerfile").read_text()
    assert "--no-access-log" in (ROOT / "deploy" / "dev-up.sh").read_text()


class Served:
    def __init__(self, server: uvicorn.Server, task: asyncio.Task[None], port: int) -> None:
        self.server, self.task, self.port = server, task, port

    async def stop(self) -> None:
        self.server.should_exit = True
        await self.task


async def _serve(subs: SubsApi) -> Served:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    config = uvicorn.Config(
        subs.api.app, host="127.0.0.1", port=port, log_config=None, access_log=False, lifespan="off"
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    for _ in range(100):
        if server.started:
            break
        await asyncio.sleep(0.05)
    return Served(server, task, port)
