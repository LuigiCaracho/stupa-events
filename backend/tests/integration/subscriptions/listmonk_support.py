"""Fixtures and builders for the Listmonk outbox, reconcile, digest and privacy tests.

`maker` is a session factory on the migrated test database (superuser: the role grants have
their own test). Every test starts with empty subscription tables.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from tests._support.fake_listmonk import FakeListmonk

KEY = "k" * 32
NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)
LATER = datetime(2099, 1, 1, tzinfo=UTC)
SUBS_TABLES = "outbox, digest_run, listmonk_list, subscription_profile, subscriber"

Maker = async_sessionmaker[AsyncSession]


@pytest_asyncio.fixture
async def maker(migrated: tuple[str, str], engine: Engine) -> AsyncIterator[Maker]:
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {SUBS_TABLES} CASCADE"))
    async_engine = create_async_engine(migrated[1])
    yield async_sessionmaker(async_engine, expire_on_commit=False, autoflush=False)
    await async_engine.dispose()


@pytest.fixture
def fake() -> FakeListmonk:
    return FakeListmonk()


class MemoryBreaker:
    """The Redis slice the circuit breaker uses."""

    def __init__(self) -> None:
        self.keys: dict[str, str] = {}

    async def exists(self, key: str) -> int:
        return int(key in self.keys)

    async def set(self, key: str, value: str, ex: int) -> None:
        self.keys[key] = value


async def add_subscriber(
    maker: Maker,
    email: str,
    *,
    status: str = "confirmed",
    categories: list[str] | None = None,
    mail: bool = True,
    created_at: datetime | None = None,
    unsubscribed_at: datetime | None = None,
    profile: bool = True,
) -> uuid.UUID:
    """Insert a subscriber with an encrypted address and, by default, its profile."""
    async with maker.begin() as session:
        sid = await session.scalar(
            text(
                "INSERT INTO subscriber (email_enc, email_hmac, status, consent_text_version, "
                "consent_categories, consent_at, confirmed_at, unsubscribed_at, created_at) "
                "VALUES (pgp_sym_encrypt(:e, :k), :h, :s, '2026-10-1', '{party}', now(), now(), "
                ":u, coalesce(:c, now())) RETURNING id"
            ),
            {
                "e": email,
                "k": KEY,
                "h": hashlib.sha256(email.encode()).hexdigest(),
                "s": status,
                "u": unsubscribed_at,
                "c": created_at,
            },
        )
        if profile:
            await session.execute(
                text(
                    "INSERT INTO subscription_profile (subscriber_id, questionnaire_version, "
                    "interests, categories, ics_token_hash, mail_enabled) "
                    "VALUES (:sid, 1, '[]', :cats, :t, :m)"
                ),
                {
                    "sid": sid,
                    "cats": categories if categories is not None else ["party"],
                    "t": uuid.uuid4().hex,
                    "m": mail,
                },
            )
    return sid


async def enqueue(
    maker: Maker,
    op: str,
    subscriber_id: uuid.UUID | None,
    *,
    payload: str = "{}",
    next_at: datetime = NOW,
) -> uuid.UUID:
    """Insert an outbox job with a unique key."""
    async with maker.begin() as session:
        return await session.scalar(
            text(
                "INSERT INTO outbox (op, subscriber_id, idempotency_key, payload, next_at) "
                "VALUES (:op, :sid, :k, CAST(:p AS jsonb), :n) RETURNING id"
            ),
            {
                "op": op,
                "sid": subscriber_id,
                "k": f"{op}:{uuid.uuid4()}",
                "p": payload,
                "n": next_at,
            },
        )


async def one(maker: Maker, sql: str, **params: Any) -> Any:
    """Run a query and return its first row."""
    async with maker() as session:
        return (await session.execute(text(sql), params)).first()


async def scalar(maker: Maker, sql: str, **params: Any) -> Any:
    """Run a query and return its first value."""
    async with maker() as session:
        return await session.scalar(text(sql), params)
