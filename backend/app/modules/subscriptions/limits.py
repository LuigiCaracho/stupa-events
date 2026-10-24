"""Abuse limits of the public subscription routes and the fixed minimum duration.

Per IP: a sliding window in Redis (fails open, like every limiter here). Per mailbox: a counter
in the database row, because Redis may be down; it never answers 429 (that would be an oracle
and a weapon against third parties) but quietly drops the mail. `constant_time` pads every
answer of the address-dependent routes to the same duration (PLAN 18, minor 2).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Final
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.settings import Settings
from app.shared.errors import RateLimitedError
from app.shared.ratelimit import RateLimiter

HOUR: Final = 3600
DAY: Final = 86400
_CLAIM_MAIL = text(
    "UPDATE subscriber SET "
    "mails_count = CASE WHEN mails_day = current_date THEN mails_count + 1 ELSE 1 END, "
    "mails_day = current_date "
    "WHERE id = :id AND NOT (mails_day = current_date AND mails_count >= :limit) "
    "RETURNING id"
)


async def hit_ip(
    limiter: RateLimiter, key: str, ip: str, *, limit: int, window: int = HOUR
) -> None:
    """Count one request of `ip` against `key`.

    Raises:
        RateLimitedError: `rate_limited` (429 with `Retry-After`) above `limit`.
    """
    result = await limiter.hit(f"subs:{key}:{ip}", limit=limit, window_seconds=window)
    if not result.allowed:
        raise RateLimitedError(
            "Zu viele Versuche. Bitte warte kurz.",
            retry_after=result.retry_after,
            code="rate_limited",
        )


async def address_allowed(limiter: RateLimiter, settings: Settings, limit_key: str) -> bool:
    """Count one mail to a mailbox (`+tag` folded away) and tell whether it may still go out."""
    result = await limiter.hit(
        f"subs:addr:{limit_key}", limit=settings.subs_mails_per_day, window_seconds=DAY
    )
    return result.allowed


async def claim_mail_slot(session: AsyncSession, settings: Settings, subscriber_id: UUID) -> bool:
    """Count one mail on the subscriber row; `False` when today's limit is used up."""
    result = await session.execute(
        _CLAIM_MAIL, {"id": subscriber_id, "limit": settings.subs_mails_per_day}
    )
    return result.first() is not None


async def constant_time(
    started: float,
    minimum: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Wait until `minimum` seconds have passed since `started` (monotonic clock)."""
    remaining = started + minimum - clock()
    if remaining > 0:
        await sleep(remaining)


@asynccontextmanager
async def padded(
    minimum: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> AsyncIterator[None]:
    """Pad the enclosed work to `minimum` seconds, errors included.

    A 429 is not padded (a limit hit does not depend on the address) and neither is a
    cancelled request.
    """
    started = clock()
    try:
        yield
    except (RateLimitedError, asyncio.CancelledError):
        raise
    except BaseException:
        await constant_time(started, minimum, clock=clock, sleep=sleep)
        raise
    else:
        await constant_time(started, minimum, clock=clock, sleep=sleep)
