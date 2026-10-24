"""Harness of the subscription route tests: the events app on a real database, the subs role.

`subs` wraps the events `api` fixture: the subscription session runs as the least-privilege
role `events_subs` (so a missing grant fails here), the settings carry the subscription keys,
the rate limiter is in memory, the mail queue records, and a test changes the settings with
`subs.configure(...)`. Mail bodies and the tokens in them are read from the recorded messages.
"""

from __future__ import annotations

import re
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
import pytest_asyncio
from httpx import Response
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.modules.notifications.mail import MailMessage
from app.modules.subscriptions.db import get_subs_session
from app.modules.subscriptions.router import mail_queue
from app.settings import Settings, get_settings
from app.shared.altcha import (
    AltchaVerifier,
    InMemoryReplayGuard,
    ReplayGuard,
    create_challenge,
    solve_challenge,
)
from app.shared.antiabuse import get_altcha_verifier, get_rate_limiter
from app.shared.ratelimit import NullRateLimiter, RateLimiter
from tests._support.factories import make_settings
from tests.integration.events.harness import Api, api, clean_events, db_roles

ADDRESS_KEY = "p" * 32
HASH_KEY = "h" * 32
ALTCHA_SECRET = "altcha-test-secret-0123"
SUBS_TABLES = "subscriber, subscription_profile, outbox, listmonk_list, digest_run"
_LINK = re.compile(r"/(?P<kind>bestaetigen|abo)/(?P<token>[A-Za-z0-9_-]{43})")


class RecordingQueue:
    """Collects the mails the routes would queue."""

    def __init__(self) -> None:
        self.sent: list[MailMessage] = []

    async def enqueue(self, msg: MailMessage) -> None:
        self.sent.append(msg)


def link_of(message: MailMessage) -> tuple[str, str]:
    """Return the kind (`bestaetigen` or `abo`) and the token of the link in a mail."""
    found = _LINK.search(message.text)
    assert found is not None, message.text
    return found["kind"], found["token"]


@dataclass
class SubsApi:
    """Typed handle around the events API fixture with the subscription wiring."""

    api: Api
    queue: RecordingQueue
    maker: async_sessionmaker[AsyncSession]
    settings: Settings
    limiter: RateLimiter = field(default_factory=NullRateLimiter)
    solver: Callable[[], str] | None = None

    def configure(self, **over: Any) -> Settings:
        """Replace the settings (the app reads them on every request)."""
        base: dict[str, Any] = {
            "pgcrypto_email_key": ADDRESS_KEY,
            "email_hash_key": HASH_KEY,
            "min_response_seconds": 0,
            "public_base_url": "https://events.example",
        }
        self.settings = make_settings(**{**base, **over})
        self.api.app.dependency_overrides[get_settings] = lambda: self.settings
        return self.settings

    def use_limiter(self, limiter: RateLimiter) -> None:
        """Use `limiter` for every route."""
        self.limiter = limiter
        self.api.app.dependency_overrides[get_rate_limiter] = lambda: limiter

    def require_altcha(
        self, replay: ReplayGuard | None = None, *, solve: bool = False
    ) -> AltchaVerifier:
        """Turn the ALTCHA check on; `solve` makes `post` bring a fresh solution itself."""
        verifier = AltchaVerifier(ALTCHA_SECRET, replay=replay or InMemoryReplayGuard())
        self.api.app.dependency_overrides[get_altcha_verifier] = lambda: verifier
        if solve:
            self.solver = lambda: solve_challenge(
                create_challenge(ALTCHA_SECRET, expires=int(time.time()) + 60, max_number=50)
            )
        return verifier

    async def post(self, path: str, body: dict[str, Any] | None = None, **kw: Any) -> Response:
        payload = body if body is not None else {}
        if self.solver is not None and "altcha" in payload and not payload["altcha"]:
            payload = {**payload, "altcha": self.solver()}
        return await self.api.client.post(path, json=payload, **kw)

    async def sql(self, statement: str, **params: Any) -> list[Any]:
        return await self.api.sql(statement, **params)

    async def scalar(self, statement: str, **params: Any) -> Any:
        rows = await self.sql(statement, **params)
        return rows[0][0] if rows else None

    def signup(
        self,
        *,
        interests: tuple[str, ...] = ("party",),
        meetings: bool = False,
        faculty: str | None = None,
        email: str | None = None,
        consent: bool = True,
        **over: Any,
    ) -> dict[str, Any]:
        """Build the body of `POST /subscriptions`."""
        mail = email is not None
        return {
            "questionnaireVersion": 1,
            "answers": {
                "interests": list(interests),
                "meetings": meetings,
                "faculty": faculty,
                "mail": mail,
            },
            "email": email,
            "consent": {"version": "2026-10-1", "accepted": consent} if mail else None,
            "altcha": "",
            **over,
        }

    async def subscribe(self, **kw: Any) -> Response:
        return await self.post("/api/public/subscriptions", self.signup(**kw))

    async def confirm(self, token: str) -> Response:
        return await self.post("/api/public/subscriptions/confirm", {"token": token})

    async def register(self, email: str, **kw: Any) -> str:
        """Sign up, confirm and return a fresh management token for `email`."""
        assert (await self.subscribe(email=email, **kw)).status_code == 202
        _, token = link_of(self.queue.sent[-1])
        assert (await self.confirm(token)).status_code == 200
        return await self.manage_token(email)

    async def manage_token(self, email: str) -> str:
        before = len(self.queue.sent)
        response = await self.post(
            "/api/public/subscriptions/manage-link", {"email": email, "altcha": ""}
        )
        assert response.status_code == 202
        assert len(self.queue.sent) == before + 1, "no management mail was queued"
        kind, token = link_of(self.queue.sent[-1])
        assert kind == "abo"
        return token

    def me(self, token: str, method: str = "GET", **kw: Any):  # noqa: ANN201
        return self.api.client.request(
            method, "/api/public/subscriptions/me", headers={"X-Subscription-Token": token}, **kw
        )


@pytest.fixture(scope="session")
def subs_url(migrated: tuple[str, str], db_roles: tuple[str, str]) -> str:
    """The async URL of the role `events_subs` (the password is set once)."""
    from sqlalchemy import create_engine

    eng = create_engine(migrated[0])
    with eng.begin() as conn:
        conn.execute(text("ALTER ROLE events_subs PASSWORD 'pw'"))
    eng.dispose()
    return migrated[1].replace("test:test", "events_subs:pw")


@pytest_asyncio.fixture
async def subs(api: Api, engine: Engine, subs_url: str) -> AsyncIterator[SubsApi]:
    """The events API with the subscription routes wired to the least-privilege role."""
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {SUBS_TABLES} RESTART IDENTITY CASCADE"))
    subs_engine = create_async_engine(subs_url)
    maker = async_sessionmaker(subs_engine, expire_on_commit=False, autoflush=False)

    async def session_override() -> AsyncIterator[AsyncSession]:
        async with maker() as session:
            yield session

    queue = RecordingQueue()
    handle = SubsApi(api, queue, maker, make_settings())
    handle.configure()
    overrides = api.app.dependency_overrides
    overrides[get_subs_session] = session_override
    overrides[mail_queue] = lambda: queue
    handle.use_limiter(NullRateLimiter())
    yield handle
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {SUBS_TABLES} RESTART IDENTITY CASCADE"))
    await subs_engine.dispose()


__all__ = [
    "ALTCHA_SECRET",
    "ADDRESS_KEY",
    "HASH_KEY",
    "Api",
    "RecordingQueue",
    "SubsApi",
    "api",
    "clean_events",
    "db_roles",
    "link_of",
    "subs",
    "subs_url",
]
