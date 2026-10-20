"""Kind catalog and the pure part of the recipient rules (contract M4, 5.7)."""

from __future__ import annotations

import pytest

from app.modules.notifications.kinds import KINDS, is_essential, is_known, kind_of
from app.modules.notifications.recipients import clean


def test_notification_kinds_essential() -> None:
    assert [k.key for k in KINDS if k.essential] == ["changes_requested"]
    assert is_essential("changes_requested")
    assert not is_essential("comment_added")


def test_mail_channels() -> None:
    assert {k.key for k in KINDS if k.mail} == {
        "review_requested",
        "changes_requested",
        "comment_added",
        "task_assigned",
        "checklist_due",
    }


def test_unknown_kind() -> None:
    assert not is_known("status_update")
    with pytest.raises(KeyError):
        kind_of("status_update")


def test_clean_drops_actor_system_and_duplicates() -> None:
    subs = ["a", "b", "a", "system:advance", "", "c"]
    assert clean(subs, "b") == ["a", "c"]


def test_clean_without_actor_keeps_order() -> None:
    assert clean(["z", "a", "z"], None) == ["z", "a"]
