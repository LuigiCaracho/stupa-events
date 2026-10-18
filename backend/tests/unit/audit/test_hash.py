"""Golden test of the audit hash chain against values computed with the upstream code."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from app.modules.audit.hashing import canonical_payload, compute_hash

_FIRST_CANONICAL = (
    b'{"action":"login","actor":"sub-1","at":"2026-10-18T09:30:00+00:00",'
    b'"data":{"method":"oidc"},"target_id":"p1","target_type":"principal"}'
)
_FIRST_HASH = "b1e94ce9b2263e0f9b10c1011428e0cd5130b526910c7c2d5e8831641d08ac42"
_SECOND_HASH = "292b5b77e59b375a1b2389ae37a7274382c2c885dcd39d833523f694659c1024"


def _first() -> bytes:
    return canonical_payload(
        actor="sub-1",
        action="login",
        target_type="principal",
        target_id="p1",
        at=datetime(2026, 10, 18, 9, 30, tzinfo=UTC),
        data={"method": "oidc"},
    )


def _second() -> bytes:
    return canonical_payload(
        actor=None,
        action="event_transition",
        target_type="event",
        target_id="e1",
        at=datetime(2026, 10, 18, 9, 31, tzinfo=timezone(timedelta(hours=2))),
        data={"to": "planning", "from": "idea", "transition": "T01", "umlaut": "Ä€"},
    )


def test_first_entry_matches_upstream_golden() -> None:
    assert _first() == _FIRST_CANONICAL
    assert compute_hash(None, _first()).hex() == _FIRST_HASH


def test_chain_matches_upstream_golden() -> None:
    first = compute_hash(None, _first())
    assert compute_hash(first, _second()).hex() == _SECOND_HASH


def test_a_changed_field_breaks_the_chain() -> None:
    tampered = canonical_payload(
        actor="sub-2",
        action="login",
        target_type="principal",
        target_id="p1",
        at=datetime(2026, 10, 18, 9, 30, tzinfo=UTC),
        data={"method": "oidc"},
    )
    assert compute_hash(None, tampered).hex() != _FIRST_HASH


def test_canonical_is_key_order_independent_and_utc_normalized() -> None:
    at = datetime(2026, 10, 18, 12, 0, tzinfo=UTC)
    local = at.astimezone(timezone(timedelta(hours=2)))
    a = canonical_payload(
        actor="a", action="x", target_type=None, target_id=None, at=at, data={"b": 1, "a": 2}
    )
    b = canonical_payload(
        actor="a", action="x", target_type=None, target_id=None, at=local, data={"a": 2, "b": 1}
    )
    assert a == b
