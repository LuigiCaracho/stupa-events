"""Limits and the minimum duration, with a fake clock."""

from __future__ import annotations

import asyncio

import pytest

from app.modules.subscriptions import limits
from app.shared.errors import RateLimitedError
from app.shared.ratelimit import InMemoryRateLimiter


class FakeClock:
    """A monotone clock that only moves when somebody sleeps."""

    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


async def test_success_waits_for_the_minimum() -> None:
    clock = FakeClock()
    async with limits.padded(0.6, clock=clock, sleep=clock.sleep):
        clock.now += 0.1
    assert clock.slept == [pytest.approx(0.5)]


async def test_an_error_waits_for_the_minimum_too() -> None:
    clock = FakeClock()
    with pytest.raises(ValueError, match="boom"):
        async with limits.padded(0.6, clock=clock, sleep=clock.sleep):
            clock.now += 0.2
            raise ValueError("boom")
    assert clock.slept == [pytest.approx(0.4)]


async def test_slow_work_is_not_padded_further() -> None:
    clock = FakeClock()
    async with limits.padded(0.6, clock=clock, sleep=clock.sleep):
        clock.now += 0.9
    assert clock.slept == []


async def test_a_limit_hit_and_a_cancellation_are_not_padded() -> None:
    clock = FakeClock()
    for error in (RateLimitedError("x", retry_after=1), asyncio.CancelledError()):
        with pytest.raises(type(error)):
            async with limits.padded(0.6, clock=clock, sleep=clock.sleep):
                raise error
    assert clock.slept == []


async def test_the_ip_limit_answers_429_with_retry_after() -> None:
    limiter = InMemoryRateLimiter(now=lambda: 1000.0)
    for _ in range(3):
        await limits.hit_ip(limiter, "ip", "1.2.3.4", limit=3)
    with pytest.raises(RateLimitedError) as err:
        await limits.hit_ip(limiter, "ip", "1.2.3.4", limit=3)
    assert err.value.status == 429 and err.value.code == "rate_limited"
    assert err.value.headers is not None and int(err.value.headers["Retry-After"]) >= 1
    await limits.hit_ip(limiter, "ip", "5.6.7.8", limit=3)
