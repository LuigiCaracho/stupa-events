"""Keyset query filters and the out schema of an audit entry (coverage of the M1 gaps)."""

from __future__ import annotations

from datetime import UTC, datetime

from app.modules.audit.models import AuditEntry
from app.modules.audit.schemas import AuditEntryOut
from app.modules.audit.service import AuditService
from tests._support.audit_fakes import fake_session, result

_AT = datetime(2026, 6, 6, 12, 0, 0, tzinfo=UTC)


def _entry(entry_id: int, prev: bytes | None = None) -> AuditEntry:
    return AuditEntry(
        id=entry_id,
        actor="a",
        action="login",
        target_type="t",
        target_id="i",
        at=_AT,
        data={},
        prev_hash=prev,
        hash=b"\x01\x02",
    )


async def test_query_cursor_applies_every_filter_and_reports_more() -> None:
    rows = [_entry(3), _entry(2), _entry(1)]
    db = fake_session(result(*rows))
    items, more = await AuditService(db).query_cursor(
        action="login", actor="a", since=_AT, until=_AT, before=9, limit=2
    )
    assert [e.id for e in items] == [3, 2] and more is True


async def test_query_cursor_without_filters_ends() -> None:
    db = fake_session(result(_entry(1)))
    items, more = await AuditService(db).query_cursor(limit=5)
    assert len(items) == 1 and more is False


def test_the_out_schema_hex_encodes_both_hashes() -> None:
    first = AuditEntryOut.from_entry(_entry(1))
    linked = AuditEntryOut.from_entry(_entry(2, prev=b"\xab"))
    assert first.hash == "0102" and first.prev_hash is None
    assert linked.prev_hash == "ab"
