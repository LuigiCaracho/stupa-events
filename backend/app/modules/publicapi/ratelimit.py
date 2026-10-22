"""Rate limits of the public routes: counted on cache misses only (contract 2.10).

A cache hit costs almost nothing, and many people share one campus IP, so only the work that
reaches the database counts. The limiter is the process-wide Redis sliding window and fails
open. Text searches count against a second, tighter key as well.
"""

from __future__ import annotations

from app.settings import Settings
from app.shared.errors import RateLimitedError
from app.shared.ratelimit import RateLimiter

WINDOW_SECONDS = 60


async def _hit(limiter: RateLimiter, key: str, limit: int) -> None:
    result = await limiter.hit(key, limit=limit, window_seconds=WINDOW_SECONDS)
    if not result.allowed:
        raise RateLimitedError(
            "Zu viele Anfragen. Bitte warte einen Moment.",
            retry_after=result.retry_after,
            code="rate_limited",
        )


async def public_limit(limiter: RateLimiter, settings: Settings, ip: str) -> None:
    """Count one cache miss of `ip` against `rl_public_per_minute`.

    Raises:
        RateLimitedError: `rate_limited` (429 with `Retry-After`) above the limit.
    """
    await _hit(limiter, f"public:ip:{ip}", settings.rl_public_per_minute)


async def search_limit(limiter: RateLimiter, settings: Settings, ip: str) -> None:
    """Count one text search miss of `ip` on top of the general count.

    Raises:
        RateLimitedError: `rate_limited` above `rl_public_search_per_minute` or the general limit.
    """
    await public_limit(limiter, settings, ip)
    await _hit(limiter, f"public-search:ip:{ip}", settings.rl_public_search_per_minute)
