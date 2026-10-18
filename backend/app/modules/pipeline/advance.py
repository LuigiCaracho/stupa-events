"""Which dossier the worker moves on, as a pure decision (contract 6).

`due_transition` reads four facts of a dossier and names the transition that is due, or
nothing. It does not decide whether the transition may run: that is `decide`, called by
`PipelineService.stage_system_fire`, so the worker has no way around the guards.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

ENDED_GRACE = timedelta(hours=12)
FOLLOWUP_GRACE = timedelta(days=30)
LIVE_INTERNAL = frozenset({"internal", "mcp"})


@dataclass(frozen=True, slots=True)
class AdvanceRow:
    """The facts of a dossier that decide whether a system transition is due."""

    state: str
    publish_at: datetime | None
    ends_at: datetime
    origin_kind: str
    entered_followup_at: datetime | None


def due_transition(row: AdvanceRow, now: datetime) -> str | None:
    """Return the id of the due system transition, or `None`.

    An `approved` dossier without `publish_at` waits for a person (D5).
    """
    match row.state:
        case "approved" if row.publish_at is not None and row.publish_at <= now:
            return "T05"
        case "live" if row.ends_at + ENDED_GRACE <= now:
            return "T08" if row.origin_kind in LIVE_INTERNAL else "T08b"
        case "followup" if (
            row.entered_followup_at is not None and row.entered_followup_at + FOLLOWUP_GRACE <= now
        ):
            return "T09b"
        case _:
            return None
