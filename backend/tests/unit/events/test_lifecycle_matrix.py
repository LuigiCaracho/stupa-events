"""The lifecycle matrix: 3 states x 7 actions x the roles, as a small table.

`allowed_actions` is the one function that decides which action a caller can try; the
service refuses everything else with 403 (right), 404 (unreadable) or 409 (state). The table
below names, per role and state, the lifecycle actions on offer.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.auth.principal import Principal
from app.modules.events.allowed import allowed_actions
from app.modules.events.editing import may_edit
from app.modules.events.models import Event
from tests._support.factories import make_principal
from tests.unit.events.test_access_and_revisions import event

ORG = uuid4()
LIFECYCLE = ("publish", "unpublish", "archive", "restore", "cancel", "postpone", "reinstate")


def person(*groups: str, sub: str = "sub-1", admin: bool = False) -> Principal:
    principal = make_principal(*groups, sub=sub, admin=admin)
    principal.bind_org_ids({"fsi": ORG})
    return principal


ROLES: dict[str, Principal] = {
    "submitter": person("events-fsi-submitter"),
    "organizer": person("events-fsi-organizer"),
    "foreign": person("events-makers-organizer"),
    "editor": person("events-editor"),
    "stupa": person("events-stupa"),
    "viewer": person("events-fsi-viewer"),
    "member": person(),
    "admin": person(admin=True),
}
EVERYTHING = {
    "draft": {"publish", "archive"},
    "published": {"unpublish", "archive", "cancel", "postpone"},
    "archived": set(),
}
EXPECTED: dict[str, dict[str, set[str]]] = {
    "submitter": {state: set() for state in EVERYTHING},
    "organizer": EVERYTHING,
    "foreign": {state: set() for state in EVERYTHING},
    "editor": {**EVERYTHING, "archived": {"restore"}},
    "stupa": {state: set() for state in EVERYTHING},
    "viewer": {state: set() for state in EVERYTHING},
    "member": {state: set() for state in EVERYTHING},
    "admin": {**EVERYTHING, "archived": {"restore"}},
}


def row(state: str, **over: object) -> Event:
    return event(**{"state": state, "organization_id": ORG, "created_by": "sub-1", **over})


def lifecycle_of(principal: Principal, state: str, **over: object) -> set[str]:
    return set(allowed_actions(principal, row(state, **over))) & set(LIFECYCLE)


@pytest.mark.parametrize("state", ["draft", "published", "archived"])
@pytest.mark.parametrize("role", ROLES)
def test_the_actions_on_offer_per_role_and_state(role: str, state: str) -> None:
    assert lifecycle_of(ROLES[role], state) == EXPECTED[role][state]


@pytest.mark.parametrize(
    ("status", "offered"),
    [
        ("scheduled", {"cancel", "postpone"}),
        ("postponed", {"cancel", "reinstate"}),
        ("cancelled", {"reinstate"}),
    ],
)
def test_the_public_status_decides_cancel_postpone_and_reinstate(
    status: str, offered: set[str]
) -> None:
    got = lifecycle_of(ROLES["organizer"], "published", public_status=status)
    assert got & {"cancel", "postpone", "reinstate"} == offered


def test_publish_requires_editor_leaves_the_click_to_the_editorial_team() -> None:
    draft = row("draft")
    assert "publish" in allowed_actions(ROLES["organizer"], draft)
    assert "publish" not in allowed_actions(ROLES["organizer"], draft, requires_editor=True)
    assert "publish" in allowed_actions(ROLES["editor"], draft, requires_editor=True)
    assert "publish" in allowed_actions(ROLES["admin"], draft, requires_editor=True)


def test_the_base_data_are_editable_in_draft_and_published_only() -> None:
    organizer, submitter = ROLES["organizer"], ROLES["submitter"]
    assert may_edit(organizer, row("draft")) and may_edit(organizer, row("published"))
    assert not may_edit(organizer, row("archived"))
    assert may_edit(submitter, row("draft"))
    assert not may_edit(submitter, row("draft", created_by="somebody-else"))
    assert not may_edit(submitter, row("published"))
    assert not may_edit(ROLES["viewer"], row("draft"))
    assert not may_edit(ROLES["foreign"], row("draft"))


def test_a_legacy_draft_without_organization_stays_editable_for_its_creator() -> None:
    orphan = row("draft", organization_id=None)
    assert may_edit(ROLES["submitter"], orphan) and may_edit(ROLES["editor"], orphan)
    assert not may_edit(person("events-fsi-organizer", sub="sub-2"), orphan)


def test_the_helper_actions_follow_state_and_right() -> None:
    draft = set(allowed_actions(ROLES["organizer"], row("draft")))
    assert {"confirm-location", "save-as-format", "revert-revision"} <= draft
    assert "verify-howto" not in draft and "clone" not in draft
    published = set(allowed_actions(ROLES["organizer"], row("published")))
    assert {"verify-howto", "clone", "save-as-format"} <= published
    archived = set(allowed_actions(ROLES["organizer"], row("archived")))
    assert "verify-howto" in archived and "clone" in archived and "revert-revision" not in archived
    assert "confirm-location" not in archived
    assert "save-as-format" not in allowed_actions(
        ROLES["organizer"], row("draft", format_id=uuid4())
    )
