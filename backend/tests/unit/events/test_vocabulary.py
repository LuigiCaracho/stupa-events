"""The Python vocabulary and the database CHECK constraints name the same values."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

from app.modules.events.models import EVENT_STATES, LEGACY_STATES, PUBLIC_STATUSES
from app.modules.events.states import EventState, PublicStatus

MIGRATION = (
    Path(__file__).resolve().parents[3] / "migrations" / "versions" / "0007_event_dossier.py"
)


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("migration_0007", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _names(sql_list: str) -> set[str]:
    return set(re.findall(r"'(\w+)'", sql_list))


def test_the_three_states_exist_in_the_migration() -> None:
    assert _names(_migration()._NEW_STATES) == {s.value for s in EventState} == set(EVENT_STATES)
    assert len(EventState) == 3


def test_the_history_accepts_both_vocabularies() -> None:
    module = _migration()
    both = _names(module._ALL_STATES)
    assert both == set(EVENT_STATES) | set(LEGACY_STATES)
    assert _names(module._OLD_STATES) | {"draft", "published"} == both


def test_public_status_values() -> None:
    assert set(PUBLIC_STATUSES) == {s.value for s in PublicStatus}
