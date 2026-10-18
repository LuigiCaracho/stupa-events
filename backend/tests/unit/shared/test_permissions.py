"""The group grammar and the role catalogue."""

from __future__ import annotations

import pytest

from app.shared.permissions import (
    PERMISSION_CATALOGUE,
    ROLE_PERMISSIONS,
    GroupGrant,
    grants_from_groups,
    parse_group,
    permissions_of,
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("events-editor", GroupGrant("editor")),
        ("events-admin", GroupGrant("admin")),
        ("events-stupa", GroupGrant("stupa")),
        ("events-fsi-organizer", GroupGrant("organizer", "fsi")),
        ("events-fsi-submitter", GroupGrant("submitter", "fsi")),
        ("events-makers-organizer", GroupGrant("organizer", "makers")),
        ("events-ekhg-approver", GroupGrant("approver", "ekhg")),
        ("events-a-b-viewer", GroupGrant("viewer", "a-b")),
    ],
)
def test_parse_group_accepts_the_grammar(name: str, expected: GroupGrant) -> None:
    assert parse_group(name) == expected


@pytest.mark.parametrize(
    "name",
    [
        "events-system:admin",
        "events-system:events-editor",
        "events-fsi-boss",
        "events--organizer",
        "Events-fsi-organizer",
        "events-fsi-organizer ",
        "fsi-organizer",
        "events-editor-extra",
        "",
    ],
)
def test_parse_group_rejects_everything_else(name: str) -> None:
    assert parse_group(name) is None


def test_grants_are_distinct_and_stable() -> None:
    groups = ["events-fsi-organizer", "events-editor", "events-fsi-organizer", "nope"]
    assert grants_from_groups(groups) == (GroupGrant("editor"), GroupGrant("organizer", "fsi"))


def test_every_role_permission_is_in_the_catalogue() -> None:
    for role, perms in ROLE_PERMISSIONS.items():
        assert perms <= set(PERMISSION_CATALOGUE), role


def test_m1_rights_per_role() -> None:
    assert "event.submit" not in permissions_of(["submitter"])
    assert "event.submit" in permissions_of(["organizer"])
    assert "event.approve" not in permissions_of(["organizer"])
    assert "event.approve" in permissions_of(["approver"])
    assert "event.image_exception" in permissions_of(["editor"])
    assert "event.image_exception" not in permissions_of(["approver"])
    assert not permissions_of(["viewer"]) & {"event.create", "event.edit"}
