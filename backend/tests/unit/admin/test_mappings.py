"""The mapping validator: every refusal of the contract (M2, 2.4) and the valid pairs."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.admin.mappings import OrgFacts, validate_group, validate_mapping

ORG = uuid4()
TRUSTED = OrgFacts(trusted=True, active=True)
PLAIN = OrgFacts(trusted=False, active=True)


@pytest.mark.parametrize(
    ("role", "org_id", "org", "code"),
    [
        ("member", None, None, "implicit_role"),
        ("editor", ORG, PLAIN, "organization_forbidden"),
        ("admin", ORG, None, "organization_forbidden"),
        ("organizer", None, None, "organization_required"),
        ("viewer", None, None, "organization_required"),
        ("organizer", ORG, None, "unknown_organization"),
        ("organizer", ORG, OrgFacts(trusted=True, active=False), "unknown_organization"),
        ("approver", ORG, PLAIN, "approver_requires_trusted"),
        ("root", None, None, "unknown_role"),
    ],
)
def test_refusals(role: str, org_id: object, org: OrgFacts | None, code: str) -> None:
    issues = validate_mapping(role, org_id, org)  # type: ignore[arg-type]
    assert [i.code for i in issues] == [code]


@pytest.mark.parametrize(
    ("role", "org_id", "org"),
    [
        ("admin", None, None),
        ("editor", None, None),
        ("stupa", None, None),
        ("viewer", ORG, PLAIN),
        ("submitter", ORG, PLAIN),
        ("organizer", ORG, PLAIN),
        ("approver", ORG, TRUSTED),
    ],
)
def test_valid_pairs(role: str, org_id: object, org: OrgFacts | None) -> None:
    assert validate_mapping(role, org_id, org) == []  # type: ignore[arg-type]


def test_the_reserved_prefix_is_refused() -> None:
    assert [i.code for i in validate_group("events-system:admin")] == ["reserved_group_prefix"]
    assert validate_group("events-system") == []
    assert validate_group("events-admin") == []
