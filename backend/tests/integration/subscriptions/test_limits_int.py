"""Limits, ALTCHA and the equal duration of the address-dependent routes."""

from __future__ import annotations

import statistics
import time

import pytest

from app.shared.altcha import create_challenge, solve_challenge
from app.shared.ratelimit import InMemoryRateLimiter
from tests.integration.subscriptions.subs_harness import (
    ALTCHA_SECRET,
    HASH_KEY,
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
ADDRESS = "ada@example.org"


async def test_the_eleventh_post_per_ip_and_hour_is_a_429_with_retry_after(subs: SubsApi) -> None:
    subs.use_limiter(InMemoryRateLimiter())
    codes = [(await subs.subscribe()).status_code for _ in range(11)]
    assert codes[:10] == [202] * 10 and codes[10] == 429
    blocked = await subs.subscribe()
    assert blocked.json()["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) >= 1 and "set-cookie" not in blocked.headers
    assert (
        await subs.post("/api/public/subscriptions/manage-link", {"email": ADDRESS})
    ).status_code == 429
    assert await subs.scalar("SELECT count(*) FROM subscription_profile") == 10


async def test_confirm_and_me_have_their_own_limits(subs: SubsApi) -> None:
    subs.configure(rl_subs_confirm_per_hour=3, rl_subs_me_per_hour=2)
    subs.use_limiter(InMemoryRateLimiter())
    codes = [(await subs.confirm("x" * 43)).status_code for _ in range(4)]
    assert codes == [404, 404, 404, 429]
    me = [(await subs.me("x" * 43)).status_code for _ in range(3)]
    assert me == [404, 404, 429]


async def test_the_fourth_mail_to_an_address_and_day_is_dropped_by_the_database_counter(
    subs: SubsApi,
) -> None:
    answers = []
    for _ in range(5):
        answers.append(await subs.subscribe(email=ADDRESS))
    assert {r.status_code for r in answers} == {202}
    assert len(subs.queue.sent) == 3
    assert await subs.scalar("SELECT mails_count FROM subscriber") == 3
    first = answers[0].json()["mail"]
    assert all(r.json()["mail"] == first for r in answers)
    await subs.sql("UPDATE subscriber SET mails_day = current_date - 1")
    await subs.subscribe(email=ADDRESS)
    assert (
        len(subs.queue.sent) == 4 and await subs.scalar("SELECT mails_count FROM subscriber") == 1
    )


async def test_plus_tag_variants_share_one_mail_budget_in_the_limiter(subs: SubsApi) -> None:
    subs.use_limiter(InMemoryRateLimiter())
    subs.configure(rl_subs_ip_per_hour=100)
    for n in range(5):
        response = await subs.subscribe(email=f"ada+{n}@example.org")
        assert response.status_code == 202
    assert len(subs.queue.sent) == 3
    assert await subs.scalar("SELECT count(*) FROM subscriber") == 5


async def test_the_magic_link_counts_against_the_same_mail_budget(subs: SubsApi) -> None:
    await subs.register(ADDRESS)
    sent = len(subs.queue.sent)
    for _ in range(4):
        await subs.post("/api/public/subscriptions/manage-link", {"email": ADDRESS, "altcha": ""})
    assert await subs.scalar("SELECT mails_count FROM subscriber") == 3
    assert len(subs.queue.sent) - sent == 1


def solved(secret: str = ALTCHA_SECRET, **kw: object) -> str:
    return solve_challenge(create_challenge(secret, max_number=50, **kw))  # type: ignore[arg-type]


async def test_altcha_is_required_checked_and_single_use(subs: SubsApi) -> None:
    subs.require_altcha()
    now = int(time.time())
    missing = await subs.subscribe()
    assert missing.status_code == 400 and missing.json()["code"] == "altcha_invalid"
    broken = await subs.subscribe(altcha="kein-base64!")
    assert broken.status_code == 400 and broken.json()["code"] == "altcha_invalid"
    wrong_secret = await subs.subscribe(altcha=solved("another-secret-0123456", expires=now + 60))
    assert wrong_secret.status_code == 400
    expired = await subs.subscribe(altcha=solved(expires=now - 10))
    assert expired.status_code == 400
    good = solved(expires=now + 60)
    assert (await subs.subscribe(altcha=good)).status_code == 202
    replay = await subs.subscribe(altcha=good)
    assert replay.status_code == 400 and replay.json()["code"] == "altcha_invalid"
    assert await subs.scalar("SELECT count(*) FROM subscription_profile") == 1


async def test_altcha_guards_the_magic_link_but_not_confirm_or_me(subs: SubsApi) -> None:
    subs.require_altcha()
    link = await subs.post("/api/public/subscriptions/manage-link", {"email": ADDRESS})
    assert link.status_code == 400
    assert (await subs.confirm("x" * 43)).status_code == 404
    assert (await subs.me("x" * 43)).status_code == 404


async def test_the_challenge_route_is_404_without_a_secret_and_a_fresh_challenge_with_one(
    subs: SubsApi,
) -> None:
    assert (await subs.api.client.get("/api/public/altcha/challenge")).status_code == 404
    subs.configure(altcha_hmac_secret=ALTCHA_SECRET)
    response = await subs.api.client.get("/api/public/altcha/challenge")
    assert response.status_code == 200 and "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"algorithm", "challenge", "salt", "signature", "maxnumber"}
    assert "expires=" in body["salt"]


async def test_the_body_is_capped_at_four_kib(subs: SubsApi) -> None:
    body = subs.signup()
    body["altcha"] = "a" * 5000
    response = await subs.post("/api/public/subscriptions", body)
    assert response.status_code in {413, 422}


def median_seconds(samples: list[float]) -> float:
    return statistics.median(samples)


async def test_known_unknown_and_unsubscribed_addresses_take_equally_long(subs: SubsApi) -> None:
    subs.configure(min_response_seconds=0.1)
    await subs.register("known@example.org")
    await subs.register("gone@example.org")
    await subs.sql(
        "UPDATE subscriber SET status = 'unsubscribed' WHERE email_hmac = :h",
        h=_hmac("gone@example.org"),
    )
    durations: dict[str, list[float]] = {"known": [], "unknown": [], "unsubscribed": []}
    for n in range(30):
        for state, address in (
            ("known", "known@example.org"),
            ("unknown", f"new{n}@example.org"),
            ("unsubscribed", "gone@example.org"),
        ):
            started = time.perf_counter()
            assert (await subs.subscribe(email=address)).status_code == 202
            durations[state].append(time.perf_counter() - started)
        await subs.sql("UPDATE subscriber SET mails_count = 0")
    medians = {state: median_seconds(values) for state, values in durations.items()}
    assert max(medians.values()) - min(medians.values()) <= 0.04, medians
    assert min(medians.values()) >= 0.1


async def test_a_confirmation_miss_and_hit_take_equally_long(subs: SubsApi) -> None:
    subs.configure(min_response_seconds=0.1)
    started = time.perf_counter()
    assert (await subs.confirm("x" * 43)).status_code == 404
    assert time.perf_counter() - started >= 0.1
    await subs.subscribe(email=ADDRESS)
    _, token = link_of(subs.queue.sent[-1])
    started = time.perf_counter()
    assert (await subs.confirm(token)).status_code == 200
    assert time.perf_counter() - started >= 0.1


def _hmac(address: str) -> str:
    from app.modules.subscriptions.emailkey import identity_hmac

    return identity_hmac(HASH_KEY, address)
