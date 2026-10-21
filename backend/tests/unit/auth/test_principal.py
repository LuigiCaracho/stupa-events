"""`Principal.has`: scope cap, admin bypass, global rights and organization rights."""

from __future__ import annotations

from uuid import uuid4

from tests._support.factories import make_principal

FSI = uuid4()
MAKERS = uuid4()


def _bound(*groups: str, admin: bool = False):
    principal = make_principal(*groups, admin=admin)
    principal.bind_org_ids({"fsi": FSI, "makers": MAKERS})
    return principal


def test_org_role_grants_only_inside_its_organization() -> None:
    principal = _bound("events-fsi-organizer")
    assert principal.has("event.publish", FSI)
    assert not principal.has("event.publish", MAKERS)
    assert not principal.has("event.publish")


def test_unbound_organization_never_matches() -> None:
    principal = make_principal("events-fsi-organizer")
    assert not principal.has("event.publish", FSI)


def test_global_editor_holds_the_right_everywhere() -> None:
    principal = _bound("events-editor")
    assert principal.has("event.publish")
    assert principal.has("event.publish", MAKERS)


def test_admin_bypasses_but_a_token_scope_still_caps() -> None:
    principal = _bound(admin=True)
    assert principal.has("event.publish", FSI)
    principal.scope_permissions = frozenset({"audit.read"})
    assert not principal.has("event.publish", FSI)
    assert principal.has("audit.read")


def test_submitter_cannot_publish() -> None:
    principal = _bound("events-fsi-submitter")
    assert principal.has("event.create", FSI)
    assert not principal.has("event.publish", FSI)


def test_slug_helpers_and_listing() -> None:
    principal = _bound("events-fsi-organizer", "events-makers-viewer")
    assert principal.org_slugs_with("event.publish") == {"fsi"}
    assert principal.has_in_org("event.publish", "fsi")
    assert not principal.has_in_org("event.publish", "makers")
    assert principal.organizations == [("fsi", "organizer"), ("makers", "viewer")]
    assert principal.in_group("events-fsi-organizer")
    assert principal.scope_allows("anything")
