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
        "events-ekhg-approver",
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
    assert "event.publish" not in permissions_of(["submitter"])
    assert {"event.publish", "event.cancel"} <= permissions_of(["organizer"])
    assert "event.restore" not in permissions_of(["organizer"])
    assert {"event.restore", "event.publish", "event.read_all"} <= permissions_of(["editor"])
    assert not permissions_of(["viewer"]) & {"event.create", "event.edit"}
    retired = {"event.submit", "event.approve", "event.image_exception", "event.assign_org"}
    assert not retired & set(PERMISSION_CATALOGUE)
    assert not set(permissions_of(["approver"]))


def test_default_mappings_follow_the_group_proposal() -> None:
    from app.shared.permissions import default_mappings

    rows = default_mappings(["fsi", "stupa"])
    groups = {(m.group, m.role, m.org) for m in rows}
    assert ("events-admin", "admin", None) in groups
    assert ("events-editor", "editor", None) in groups
    assert ("events-stupa", "stupa", None) in groups
    assert {"events-fsi-viewer", "events-fsi-submitter", "events-fsi-organizer"} <= {
        g for g, _, _ in groups
    }
    assert not {g for g, _, _ in groups if g.endswith("-approver")}
    assert len(rows) == 3 + 3 + 3


def test_the_admin_role_maintains_venues() -> None:
    from app.shared.permissions import ROLE_PERMISSIONS

    assert "venue.manage" in ROLE_PERMISSIONS["admin"]
    assert "admin.mappings" not in ROLE_PERMISSIONS["editor"]
