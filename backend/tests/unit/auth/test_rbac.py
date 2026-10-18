"""RBAC resolution with a fake session: groups, reserved names, mappings and trust."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.auth import rbac
from tests._support.factories import make_settings


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows

    def scalars(self) -> _Rows:
        return self


class FakeDb:
    """Answers the two resolver queries: group mappings first, then the trusted slugs."""

    def __init__(self, mapped: list[tuple[str, str | None]], trusted: list[str]) -> None:
        self.mapped = mapped
        self.trusted = trusted
        self.calls = 0

    async def execute(self, statement: Any) -> _Rows:
        self.calls += 1
        sql = str(statement)
        if "group_mapping" in sql:
            return _Rows(self.mapped)
        return _Rows(self.trusted)


def _row(groups: list[str], **extra: Any) -> Any:
    return SimpleNamespace(
        sub="sub-1",
        email="a@b.de",
        display_name="A",
        oidc_groups=groups,
        bootstrap_admin=extra.get("bootstrap_admin", False),
    )


async def _resolve(groups: list[str], db: FakeDb | None = None, **extra: Any):
    return await rbac.resolve_principal(
        db or FakeDb([], []), _row(groups, **extra), make_settings(**extra.get("settings", {}))
    )


async def test_global_and_org_roles_come_from_the_group_names() -> None:
    principal = await _resolve(["events-editor", "events-fsi-organizer", "random"])
    assert principal.roles == ["editor", "member"]
    assert principal.org_roles == {"fsi": frozenset({"organizer"})}
    assert "event.approve" in principal.permissions
    assert principal.groups == {"events-editor", "events-fsi-organizer", "random"}


async def test_reserved_namespace_never_enters_the_group_set() -> None:
    principal = await _resolve(["events-system:events-editor", "events-system:x"])
    assert principal.roles == ["member"]
    assert principal.groups == set()


async def test_no_groups_means_member_only_and_no_query() -> None:
    db = FakeDb([], [])
    principal = await rbac.resolve_principal(db, _row([]), make_settings())
    assert principal.roles == ["member"]
    assert db.calls == 0


async def test_approver_of_an_untrusted_org_falls_back_to_organizer() -> None:
    principal = await _resolve(
        ["events-fsi-approver", "events-makers-approver"], FakeDb([], ["makers"])
    )
    assert principal.org_roles == {
        "fsi": frozenset({"organizer"}),
        "makers": frozenset({"approver"}),
    }


async def test_group_mapping_adds_grants_and_ignores_invalid_ones() -> None:
    db = FakeDb([("organizer", "fsi"), ("editor", None), ("approver", None), ("editor", "fsi")], [])
    principal = await _resolve(["Campus-Gruppe"], db)
    assert principal.roles == ["editor", "member"]
    assert principal.org_roles == {"fsi": frozenset({"organizer"})}


@pytest.mark.parametrize(
    ("flag", "settings", "expected"),
    [
        (True, {"bootstrap_admin_subjects": "sub-1"}, True),
        (True, {"bootstrap_admin_emails": "A@B.de"}, True),
        (True, {}, False),
        (False, {"bootstrap_admin_subjects": "sub-1"}, False),
    ],
)
async def test_bootstrap_admin_needs_flag_and_list(
    flag: bool, settings: dict[str, str], expected: bool
) -> None:
    principal = await rbac.resolve_principal(
        FakeDb([], []), _row([], bootstrap_admin=flag), make_settings(**settings)
    )
    assert ("admin" in principal.roles) is expected
