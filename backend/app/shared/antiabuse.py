"""Anti-abuse wiring for write endpoints.

The FastAPI dependencies here run before the endpoint logic. They enforce a body cap
(413) and the rate limits (429 with ``Retry-After``). The rate limiter builds from the
injected ``Settings`` and caches lazily on ``app.state``, so tests can replace it through
``dependency_overrides``. ALTCHA guards the public forms (stage B): the solution travels in
the JSON body and the verifier checks it locally.

These are dependencies and not middleware on purpose. Each route can then set its own
throttle, and the OpenAPI contract shows the behavior.

Copied from STUPA-Workflow@93c33d6 backend/app/shared/antiabuse.py (reduced to M1, plus ALTCHA)
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request

from app.deps import Principal, get_current_principal
from app.settings import Settings, get_settings
from app.shared.altcha import AltchaError, AltchaVerifier, NullAltchaVerifier, RedisReplayGuard
from app.shared.errors import BadRequestError, PayloadTooLargeError, RateLimitedError
from app.shared.ratelimit import NullRateLimiter, RateLimiter, RedisRateLimiter

SettingsDep = Annotated[Settings, Depends(get_settings)]
_HOUR = 3600
_MULTIPART_OVERHEAD_BYTES = 64 * 1024


def client_ip(request: Request) -> str:
    """Return the client IP for the rate-limit key.

    Behind the reverse proxy, uvicorn ``--proxy-headers`` puts the real IP into
    ``request.client.host``. It accepts X-Forwarded-For only from the trusted proxies in
    ``FORWARDED_ALLOW_IPS``. This function therefore parses no header itself.
    """
    return request.client.host if request.client is not None else "unknown"


def _redis_client(request: Request, settings: Settings) -> object:
    state = request.app.state
    client = getattr(state, "_antiabuse_redis", None)
    if client is None:
        import redis.asyncio as aioredis

        client = aioredis.from_url(
            settings.redis_url,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
        )
        state._antiabuse_redis = client
    return client


def get_rate_limiter(request: Request, settings: SettingsDep) -> RateLimiter:
    """Return the process-wide rate limiter (Redis, or a no-op when disabled)."""
    state = request.app.state
    limiter = getattr(state, "_rate_limiter", None)
    if limiter is None:
        limiter = (
            RedisRateLimiter(_redis_client(request, settings))
            if settings.rate_limit_enabled
            else NullRateLimiter()
        )
        state._rate_limiter = limiter
    return limiter


def get_altcha_verifier(
    request: Request, settings: SettingsDep
) -> AltchaVerifier | NullAltchaVerifier:
    """Return the process-wide verifier (the no-op one while no secret is set)."""
    state = request.app.state
    verifier = getattr(state, "_altcha_verifier", None)
    if verifier is None:
        if settings.altcha_enabled:
            assert settings.altcha_hmac_secret is not None
            verifier = AltchaVerifier(
                settings.altcha_hmac_secret,
                replay=RedisReplayGuard(_redis_client(request, settings)),
                replay_ttl_seconds=settings.altcha_challenge_ttl_seconds,
            )
        else:
            verifier = NullAltchaVerifier()
        state._altcha_verifier = verifier
    return verifier


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
AltchaDep = Annotated["AltchaVerifier | NullAltchaVerifier", Depends(get_altcha_verifier)]


def body_cap(limit_attr: str) -> Callable[[Request, Settings], None]:
    """Make a dependency that answers 413 when the request body is too large.

    The dependency compares ``Content-Length`` against ``Settings.<limit_attr>``. This
    is defense in depth. The authoritative limit is nginx ``client_max_body_size`` at
    the edge; a chunked request carries no ``Content-Length``.
    """

    def dependency(request: Request, settings: SettingsDep) -> None:
        limit = int(getattr(settings, limit_attr))
        raw = request.headers.get("content-length")
        if raw is not None and raw.isdigit() and int(raw) > limit:
            raise PayloadTooLargeError(f"Request body exceeds {limit} bytes.")

    return dependency


def enforce_attachment_body_cap(request: Request, settings: SettingsDep) -> None:
    """Answer 413 when the ``Content-Length`` of an upload is clearly too large.

    The limit is ``attachment_max_bytes`` plus room for the multipart frame. The route
    reads the file under the authoritative cap, also for a chunked body.
    """
    limit = settings.attachment_max_bytes + _MULTIPART_OVERHEAD_BYTES
    raw = request.headers.get("content-length")
    if raw is not None and raw.isdigit() and int(raw) > limit:
        raise PayloadTooLargeError(f"Request body exceeds {limit} bytes.")


async def _enforce(limiter: RateLimiter, key: str, *, limit: int, window: int, detail: str) -> None:
    result = await limiter.hit(key, limit=limit, window_seconds=window)
    if not result.allowed:
        raise RateLimitedError(detail, retry_after=result.retry_after)


async def rate_limit_attachments(
    request: Request,
    settings: SettingsDep,
    limiter: RateLimiterDep,
    principal: Annotated[Principal | None, Depends(get_current_principal)],
) -> None:
    """Throttle uploads to ``rl_attachments_per_hour`` per principal (IP without one).

    The auth dependency (401/403) runs separately. This dependency only throttles the
    frequency.
    """
    key = (
        f"attachments:principal:{principal.sub}"
        if principal is not None
        else f"attachments:ip:{client_ip(request)}"
    )
    await _enforce(
        limiter,
        key,
        limit=settings.rl_attachments_per_hour,
        window=_HOUR,
        detail="Too many uploads. Try again later.",
    )


async def rate_limit_media_images(
    settings: SettingsDep,
    limiter: RateLimiterDep,
    principal: Annotated[Principal | None, Depends(get_current_principal)],
) -> None:
    """Throttle image uploads to ``rl_media_images_per_hour`` per principal.

    Only a principal may upload. The route answers 401 without one; this dependency
    then does nothing. Every upload costs a Pillow decode.
    """
    if principal is None:
        return
    await _enforce(
        limiter,
        f"media-images:principal:{principal.sub}",
        limit=settings.rl_media_images_per_hour,
        window=_HOUR,
        detail="Too many uploads. Try again later.",
    )


async def rate_limit_search(
    settings: SettingsDep,
    limiter: RateLimiterDep,
    principal: Annotated[Principal | None, Depends(get_current_principal)],
) -> None:
    """Throttle the internal search to ``rl_search_per_minute`` per principal.

    The palette asks at every key press, so the budget is generous. The route answers 401
    without a principal; this dependency then does nothing.
    """
    if principal is None:
        return
    await _enforce(
        limiter,
        f"search:principal:{principal.sub}",
        limit=settings.rl_search_per_minute,
        window=60,
        detail="Too many searches. Try again later.",
    )


async def verify_altcha_solution(
    verifier: AltchaVerifier | NullAltchaVerifier, solution: str
) -> None:
    """Verify one solution.

    Raises:
        BadRequestError: `altcha_invalid` for a missing, wrong, expired or reused solution.
    """
    try:
        await verifier.verify(solution or None)
    except AltchaError as exc:
        raise BadRequestError("Altcha verification failed.", code="altcha_invalid") from exc


def now_unix() -> int:
    """Return the current time in unix seconds."""
    return int(time.time())
