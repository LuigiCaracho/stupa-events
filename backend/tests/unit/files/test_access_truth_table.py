"""Who reads an attachment: role x visibility x kind (PLAN 5.4, contract 3.7)."""

from __future__ import annotations

import uuid

import pytest

from app.modules.auth.principal import Principal
from app.modules.files.access import attachment_readable, readable_clause
from app.modules.files.models import ATTACHMENT_KINDS, RESTRICTED_KINDS, VISIBILITIES
from app.shared.permissions import permissions_of

ORG = uuid.uuid4()
OTHER_ORG = uuid.uuid4()


def person(global_role: str | None = None, org_role: str | None = None) -> Principal:
    roles = [global_role] if global_role else []
    principal = Principal(
        sub="sub",
        roles=roles,
        permissions=set(permissions_of(roles)),
        org_roles={"fsi": frozenset({org_role})} if org_role else {},
    )
    principal.bind_org_ids({"fsi": ORG})
    return principal


#: role -> (reads team files, reads restricted kinds)
ORACLE = {
    "viewer": (False, False),
    "member": (False, False),
    "submitter": (False, True),
    "organizer": (True, True),
    "approver": (True, True),
    "stupa": (False, True),
    "editor": (True, True),
    "admin": (True, True),
}
ROLES = {
    "viewer": person(org_role="viewer"),
    "member": person("member"),
    "submitter": person(org_role="submitter"),
    "organizer": person(org_role="organizer"),
    "approver": person(org_role="approver"),
    "stupa": person("stupa"),
    "editor": person("editor"),
    "admin": person("admin"),
}


@pytest.mark.parametrize("role", ORACLE)
@pytest.mark.parametrize("visibility", VISIBILITIES)
@pytest.mark.parametrize("kind", ATTACHMENT_KINDS)
def test_attachment_readable_truth_table(role: str, visibility: str, kind: str) -> None:
    team, restricted = ORACLE[role]
    expected = (visibility != "team" or team) and (kind not in RESTRICTED_KINDS or restricted)
    assert attachment_readable(ROLES[role], ORG, kind, visibility) is expected


def test_a_role_of_another_organization_reads_nothing_restricted_there() -> None:
    outsider = person(org_role="organizer")
    assert not attachment_readable(outsider, OTHER_ORG, "quote", "org")
    assert not attachment_readable(outsider, OTHER_ORG, "other", "team")
    assert attachment_readable(outsider, OTHER_ORG, "other", "org")


def test_the_sql_clause_names_the_same_visibilities_as_the_function() -> None:
    for role, principal in ROLES.items():
        text = str(readable_clause(principal, ORG).compile(compile_kwargs={"literal_binds": True}))
        team, restricted = ORACLE[role]
        assert ("'team'" in text) is team, role
        assert ("quote" in text) is (not restricted), role
