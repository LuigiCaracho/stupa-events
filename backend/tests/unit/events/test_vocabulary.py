"""The Python vocabulary and the database CHECK constraints name the same values."""

from __future__ import annotations

import re
from pathlib import Path

from app.modules.events.models import EVENT_STATES, PUBLIC_STATUSES
from app.modules.events.states import EventState, PublicStatus

MIGRATION = Path(__file__).resolve().parents[3] / "migrations" / "versions" / "0002_events_core.py"


def test_all_eight_states_exist_in_the_migration() -> None:
    text = MIGRATION.read_text()
    match = re.search(r"_STATES = \"([^\"]+)\"", text)
    assert match is not None
    in_migration = set(re.findall(r"'(\w+)'", match.group(1)))
    assert in_migration == {s.value for s in EventState} == set(EVENT_STATES)
    assert len(EventState) == 8


def test_public_status_values() -> None:
    assert set(PUBLIC_STATUSES) == {s.value for s in PublicStatus}
