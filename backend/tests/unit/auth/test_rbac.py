"""RBAC resolution with a fake session: only `group_mapping` decides."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.modules.auth import rbac
from tests._support.factories import make_settings

FSI, MAKERS = uuid4(), uuid4()
ORG_IDS = {"fsi": FSI, "makers": MAKERS}


class _Rows:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return self._rows


class FakeDb:
    """Answers the one resolver query with `(role, org id, slug, group)` rows."""

    def __init__(self, mapped: list[tuple[str, str | None]]) -> None:
        self.mapped = mapped
        self.calls = 0

    async def execute(self, statement: Any) -> _Rows:
        self.calls += 1
        assert "group_mapping" in str(statement)
        group = sorted(statement.compile().params["oidc_group_1"])[0]
        return _Rows([(role, ORG_IDS.get(slug or ""), slug, group) for role, slug in self.mapped])


def _row(groups: list[str], **extra: Any) -> Any:
    return SimpleNamespace(
        sub="sub-1",
        email="a@b.de",
        display_name="A",
        oidc_groups=groups,
        bootstrap_admin=extra.get("bootstrap_admin", False),
    )


async def _resolve(groups: list[str], mapped: list[tuple[str, str | None]] | None = None):
    return await rbac.resolve_principal(FakeDb(mapped or []), _row(groups), make_settings())


async def test_a_group_name_alone_grants_nothing() -> None:
    principal = await _resolve(["events-editor", "events-fsi-organizer", "random"])
    assert principal.roles == ["member"]
    assert principal.org_roles == {}
    assert principal.groups == {"events-editor", "events-fsi-organizer", "random"}


async def test_mapping_rows_grant_global_and_org_roles_and_bind_the_ids() -> None:
    principal = await _resolve(["Campus"], [("editor", None), ("organizer", "fsi")])
    assert principal.roles == ["editor", "member"]
    assert principal.org_roles == {"fsi": frozenset({"organizer"})}
    assert principal.org_ids == {"fsi": str(FSI)}
    assert principal.has("event.restore") and principal.has("event.create", FSI)


async def test_reserved_namespace_never_enters_the_group_set() -> None:
    principal = await _resolve(["events-system:events-editor", "events-system:x"])
    assert principal.roles == ["member"]
    assert principal.groups == set()


async def test_no_groups_means_member_only_and_no_query() -> None:
    db = FakeDb([])
    principal = await rbac.resolve_principal(db, _row([]), make_settings())
    assert principal.roles == ["member"]
    assert db.calls == 0


async def test_the_retired_role_approver_grants_nothing() -> None:
    principal = await _resolve(["g"], [("approver", "fsi")])
    assert principal.org_roles == {}


async def test_rows_with_a_role_that_does_not_fit_their_scope_are_ignored() -> None:
    principal = await _resolve(["g"], [("organizer", None), ("editor", "fsi"), ("viewer", "fsi")])
    assert principal.roles == ["member"]
    assert principal.org_roles == {"fsi": frozenset({"viewer"})}


async def test_two_groups_in_one_org_give_both_roles() -> None:
    principal = await _resolve(["a", "b"], [("viewer", "fsi"), ("submitter", "fsi")])
    assert principal.org_roles == {"fsi": frozenset({"viewer", "submitter"})}


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
        FakeDb([]), _row([], bootstrap_admin=flag), make_settings(**settings)
    )
    assert ("admin" in principal.roles) is expected
