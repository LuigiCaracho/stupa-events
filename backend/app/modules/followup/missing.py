"""What still blocks T09: the parts of the follow-up that are not done (for mails and cards)."""

from __future__ import annotations

from datetime import datetime

from app.modules.pipeline.snapshot import Snapshot


def missing_of(snapshot: Snapshot) -> list[str]:
    """Name the open parts of the follow-up, in the order of the T09 guards."""
    done = (
        ("checklist", snapshot.open_required_followup == 0),
        ("retrospective", snapshot.retrospective_filled),
        ("outcome", snapshot.outcome_set),
        ("howto", snapshot.howto_verified),
    )
    return [name for name, ok in done if not ok]


def days_open(entered: datetime | None, now: datetime) -> int:
    """Return the full days since the dossier entered `followup` (0 when unknown)."""
    return 0 if entered is None else max((now - entered).days, 0)
