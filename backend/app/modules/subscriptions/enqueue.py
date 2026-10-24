"""The one bridge from the subscription flows to the Listmonk outbox.

`enqueue_outbox` only inserts; the worker brings Listmonk to the wanted state later, so a
flow never waits for Listmonk. The idempotency key is `<op>:<subscriber id>:<profile version>`
with the version being the profile's `updated_at` in microseconds: the same change queued twice
collapses into one row, a later change gets a new key.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import Text, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)
_INSERT = text(
    "INSERT INTO outbox (op, subscriber_id, idempotency_key, payload) "
    "VALUES (:op, :sid, :key, :payload) ON CONFLICT (idempotency_key) DO NOTHING"
).bindparams(bindparam("payload", type_=JSONB), bindparam("key", type_=Text))
_VERSION = text("SELECT updated_at FROM subscription_profile WHERE subscriber_id = :sid")


async def enqueue_outbox(
    session: AsyncSession,
    *,
    op: str,
    subscriber_id: UUID,
    payload: dict[str, Any] | None = None,
) -> None:
    """Queue `op` for the subscriber unless the same change is already queued."""
    updated = (await session.execute(_VERSION, {"sid": subscriber_id})).scalar()
    version = 0 if updated is None else (updated - _EPOCH) // _MICROSECOND
    await session.execute(
        _INSERT,
        {
            "op": op,
            "sid": subscriber_id,
            "key": f"{op}:{subscriber_id}:{version}",
            "payload": payload or {},
        },
    )
