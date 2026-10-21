"""Validation of the account notification settings."""

from __future__ import annotations

import pytest

from app.modules.account.schemas import PrefIn
from app.modules.account.service import validate_prefs
from app.modules.notifications import kinds
from app.shared.errors import ValidationProblem


def test_valid_subset() -> None:
    validate_prefs([PrefIn(kind="comment_added", in_app=False, mail=False)])
    validate_prefs([PrefIn(kind="published", in_app=True, mail=True)])


def test_every_kind_can_go_off_because_none_is_essential() -> None:
    validate_prefs([PrefIn(kind=k.key, in_app=False, mail=False) for k in kinds.KINDS])


def test_an_essential_kind_cannot_go_off(monkeypatch: pytest.MonkeyPatch) -> None:
    fixed = kinds.Kind("fixed", mail=True, essential=True)
    monkeypatch.setitem(kinds._BY_KEY, "fixed", fixed)
    with pytest.raises(ValidationProblem) as err:
        validate_prefs([PrefIn(kind="fixed", in_app=True, mail=False)])
    assert err.value.code == "kind_essential"


def test_unknown_kind() -> None:
    with pytest.raises(ValidationProblem) as err:
        validate_prefs([PrefIn(kind="status_update", in_app=True, mail=True)])
    assert err.value.code == "unknown_kind"
