"""The audit chain against a real database: appends, verification and tampering."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.audit.service import AuditService, record

pytestmark = pytest.mark.integration


async def test_chain_of_appends_verifies(session: AsyncSession) -> None:
    for i in range(5):
        await record(session, actor=f"sub-{i}", action=AuditAction.LOGIN, data={"i": i})
    await session.commit()
    result = await AuditService(session).verify_chain()
    assert result.valid and result.checked == 5


async def test_first_entry_has_no_predecessor_and_links_follow(session: AsyncSession) -> None:
    first = await record(session, actor="a", action="login")
    second = await record(session, actor="a", action="login")
    await session.commit()
    assert first.prev_hash is None
    assert second.prev_hash == first.hash


async def test_concurrent_appends_keep_one_chain(migrated: tuple[str, str], engine: Engine) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    async_engine = create_async_engine(migrated[1])
    maker = async_sessionmaker(async_engine, expire_on_commit=False)

    async def one(i: int) -> None:
        async with maker() as db:
            await record(db, actor=f"s{i}", action="login", data={"i": i})
            await db.commit()

    await asyncio.gather(*(one(i) for i in range(12)))
    async with maker() as db:
        result = await AuditService(db).verify_chain()
    await async_engine.dispose()
    assert result.valid and result.checked == 12


async def test_a_bypassed_tamper_is_caught_by_verification(
    session: AsyncSession, engine: Engine
) -> None:
    for i in range(3):
        await record(session, actor="a", action="login", data={"i": i})
    await session.commit()
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE audit_entry DISABLE TRIGGER trg_audit_entry_no_update"))
        conn.execute(text("UPDATE audit_entry SET actor = 'mallory' WHERE id = 2"))
        conn.execute(text("ALTER TABLE audit_entry ENABLE TRIGGER trg_audit_entry_no_update"))
    result = await AuditService(session).verify_chain()
    assert not result.valid
    assert (result.broken_at, result.reason) == (2, "hash_mismatch")


async def test_verify_and_store_keeps_the_result(session: AsyncSession) -> None:
    await record(session, actor="a", action="login")
    await session.commit()
    service = AuditService(session)
    row = await service.verify_and_store(trigger="cron")
    latest = await service.latest_verification()
    assert row.valid and latest is not None and latest.id == row.id and latest.checked == 1
