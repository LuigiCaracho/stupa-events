"""`actor_of` and `kind_of`: kind and Four-Eyes binding, derived without `principal.roles`."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.modules.pipeline.actor import actor_of, kind_of
from app.modules.pipeline.snapshot import SYSTEM_ACTOR, SYSTEM_SUB
from tests._support.factories import make_principal

ORG = uuid4()


def bound(*groups: str, admin: bool = False, sub: str = "s"):  # noqa: ANN202
    principal = make_principal(*groups, admin=admin, sub=sub)
    principal.bind_org_ids({"fsi": ORG, "stupa": uuid4()})
    return principal


@pytest.mark.parametrize(
    ("groups", "admin", "kind"),
    [
        (("events-editor",), False, "editor"),
        (("events-editor",), True, "editor"),
        ((), True, "admin"),
        (("events-fsi-organizer",), False, "org"),
        ((), False, "org"),
    ],
)
def test_kind(groups: tuple[str, ...], admin: bool, kind: str) -> None:
    assert kind_of(bound(*groups, admin=admin)) == kind


def test_editor_four_eyes_follows_the_setting() -> None:
    editor = bound("events-editor")
    assert actor_of(editor, ORG, editor_four_eyes=False).four_eyes is False
    assert actor_of(editor, ORG, editor_four_eyes=True).four_eyes is True


def test_org_roles_and_admin_are_always_bound() -> None:
    assert actor_of(bound("events-fsi-organizer"), ORG, False).four_eyes is True
    assert actor_of(bound(admin=True), ORG, False).four_eyes is True


def test_the_setting_is_the_default(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests._support.factories import make_settings

    monkeypatch.setattr(
        "app.modules.pipeline.actor.get_settings", lambda: make_settings(editor_four_eyes=True)
    )
    assert actor_of(bound("events-editor"), ORG).four_eyes is True


def test_permissions_are_those_held_in_the_organization() -> None:
    actor = actor_of(bound("events-fsi-organizer"), ORG, False)
    assert actor.can("event.submit") and not actor.can("event.approve")
    assert not actor_of(bound("events-fsi-organizer"), uuid4(), False).can("event.submit")


def test_system_actor() -> None:
    assert SYSTEM_ACTOR.sub == SYSTEM_SUB == "system:advance_states"
    assert SYSTEM_ACTOR.kind == "system" and not SYSTEM_ACTOR.permissions
    assert SYSTEM_ACTOR.four_eyes is False
