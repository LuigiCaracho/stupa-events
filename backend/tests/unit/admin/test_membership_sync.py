"""Membership sync with a fake database: add, remove, idempotence, inactive people."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.modules.admin import membership_sync
from app.modules.audit.actions import AuditAction
from app.modules.auth import rbac

FSI, MAKERS = uuid4(), uuid4()
PERSON = uuid4()


class SyncDb:
    """Holds the `membership` rows in memory; mappings arrive through the patched loader."""

    def __init__(self, mappings: list[tuple[str, str, str | None]]) -> None:
        self.mappings = mappings
        self.held: set[tuple[UUID, str]] = set()

    def rows(self) -> list[tuple[str, UUID | None, str | None, str]]:
        ids = {"fsi": FSI, "makers": MAKERS}
        return [(role, ids.get(slug or ""), slug, group) for group, role, slug in self.mappings]

    async def execute(self, statement: Any) -> Any:
        sql = str(statement)
        params = statement.compile().params
        if sql.startswith("DELETE"):
            self.held.discard((params["organization_id_1"], params["role_1"]))
            return SimpleNamespace()
        if sql.startswith("INSERT"):
            self.held.add((params["organization_id"], params["role"]))
            return SimpleNamespace()
        return SimpleNamespace(all=lambda: sorted(self.held, key=str))

    async def flush(self) -> None:
        return None


@pytest.fixture(autouse=True)
def mapping_loader(monkeypatch: pytest.MonkeyPatch) -> None:
    async def load(db: SyncDb) -> Any:
        return db.rows()

    monkeypatch.setattr(membership_sync, "load_mappings", load)
    monkeypatch.setattr(rbac, "load_mappings", load)


@pytest.fixture
def audits(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    seen: list[dict[str, Any]] = []

    async def record(_db: Any, **kwargs: Any) -> None:
        seen.append(kwargs)

    monkeypatch.setattr(membership_sync, "audit_record", record)
    return seen


def _person(groups: list[str], *, active: bool = True) -> Any:
    return SimpleNamespace(id=PERSON, oidc_groups=groups, active=active)


MAPPINGS = [
    ("g-fsi-org", "organizer", "fsi"),
    ("g-fsi-sub", "submitter", "fsi"),
    ("g-makers-sub", "submitter", "makers"),
    ("g-editor", "editor", None),
]


async def test_a_group_adds_a_membership_and_audits_it(audits: list[dict[str, Any]]) -> None:
    db = SyncDb(MAPPINGS)
    assert await membership_sync.sync_principal_memberships(db, _person(["g-fsi-org"]))
    assert db.held == {(FSI, "organizer")}
    assert audits == [
        {
            "actor": "oidc-sync",
            "action": AuditAction.ROLE_CHANGE,
            "target_type": "membership",
            "target_id": str(FSI),
            "data": {"principalId": str(PERSON), "role": "organizer", "change": "added"},
        }
    ]


async def test_removing_the_group_removes_the_membership(audits: list[dict[str, Any]]) -> None:
    db = SyncDb(MAPPINGS)
    await membership_sync.sync_principal_memberships(db, _person(["g-fsi-org"]))
    assert await membership_sync.sync_principal_memberships(db, _person([]))
    assert db.held == set()
    assert [a["data"]["change"] for a in audits] == ["added", "removed"]


async def test_groups_of_two_organizations_give_two_memberships(
    audits: list[dict[str, Any]],
) -> None:
    db = SyncDb(MAPPINGS)
    await membership_sync.sync_principal_memberships(db, _person(["g-fsi-sub", "g-makers-sub"]))
    assert db.held == {(FSI, "submitter"), (MAKERS, "submitter")}


async def test_a_second_run_changes_nothing(audits: list[dict[str, Any]]) -> None:
    db = SyncDb(MAPPINGS)
    person = _person(["g-fsi-org", "g-editor"])
    assert await membership_sync.sync_principal_memberships(db, person) is True
    audits.clear()
    assert await membership_sync.sync_principal_memberships(db, person) is False
    assert audits == [] and db.held == {(FSI, "organizer")}


async def test_two_groups_of_one_org_keep_both_roles(audits: list[dict[str, Any]]) -> None:
    db = SyncDb(MAPPINGS)
    await membership_sync.sync_principal_memberships(db, _person(["g-fsi-org", "g-fsi-sub"]))
    assert db.held == {(FSI, "organizer"), (FSI, "submitter")}


async def test_a_deactivated_person_holds_nothing(audits: list[dict[str, Any]]) -> None:
    db = SyncDb(MAPPINGS)
    await membership_sync.sync_principal_memberships(db, _person(["g-fsi-org"]))
    assert await membership_sync.sync_principal_memberships(
        db, _person(["g-fsi-org"], active=False)
    )
    assert db.held == set()


async def test_the_reserved_namespace_has_no_effect(audits: list[dict[str, Any]]) -> None:
    mappings = [("events-system:g-fsi-org", "organizer", "fsi"), *MAPPINGS]
    db = SyncDb(mappings)
    assert not await membership_sync.sync_principal_memberships(
        db, _person(["events-system:g-fsi-org"])
    )
    assert db.held == set() and audits == []


async def test_no_groups_means_no_resolver_query(audits: list[dict[str, Any]]) -> None:
    grants = await rbac.effective_grants(SyncDb(MAPPINGS), [])
    assert grants.global_roles == frozenset() and grants.org_roles == {}


async def test_sync_all_runs_for_every_person(
    monkeypatch: pytest.MonkeyPatch, audits: list[dict[str, Any]]
) -> None:
    people = [SimpleNamespace(sub="a"), SimpleNamespace(sub="b"), SimpleNamespace(sub="c")]
    ran: list[Any] = []

    async def fake_sync(_db: Any, row: Any, _mappings: Any) -> bool:
        ran.append(row)
        return row.sub != "b"

    class Db(SyncDb):
        async def execute(self, statement: Any) -> Any:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: people))

    monkeypatch.setattr(membership_sync, "sync_principal_memberships", fake_sync)
    assert await membership_sync.sync_all_memberships(Db([])) == 2
    assert ran == people
