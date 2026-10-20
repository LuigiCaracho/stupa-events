"""Validation of the account notification settings."""

from __future__ import annotations

import pytest

from app.modules.account.schemas import PrefIn
from app.modules.account.service import validate_prefs
from app.shared.errors import ValidationProblem


def test_valid_subset() -> None:
    validate_prefs([PrefIn(kind="comment_added", in_app=False, mail=False)])
    validate_prefs([PrefIn(kind="changes_requested", in_app=True, mail=True)])


def test_essential_kind_cannot_go_off() -> None:
    with pytest.raises(ValidationProblem) as err:
        validate_prefs([PrefIn(kind="changes_requested", in_app=True, mail=False)])
    assert err.value.code == "kind_essential"


def test_unknown_kind() -> None:
    with pytest.raises(ValidationProblem) as err:
        validate_prefs([PrefIn(kind="status_update", in_app=True, mail=True)])
    assert err.value.code == "unknown_kind"
