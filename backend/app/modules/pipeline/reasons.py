"""`Reason`: one blocker or warning of a guard, shown before the click (PLAN 4.4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Severity(StrEnum):
    """Weight of a reason; only a blocker stops a transition."""

    BLOCKER = "blocker"
    WARNING = "warning"


class FixAction(StrEnum):
    """The one-click remedy the UI offers for a reason."""

    FILL_FIELD = "fill_field"
    CHANGE_DATE = "change_date"
    UPLOAD_POSTER = "upload_poster"


@dataclass(frozen=True, slots=True)
class Reason:
    """Why a guard refuses (or warns). `message_key` is an i18n key `guards.<code>`."""

    code: str
    field: str | None
    severity: Severity
    message_key: str
    fix_action: FixAction | None


def blocker(code: str, *, field: str | None = None, fix: FixAction | None = None) -> Reason:
    """Build a blocking reason with the message key `guards.<code>`."""
    return Reason(code, field, Severity.BLOCKER, f"guards.{code}", fix)


def blockers(reasons: list[Reason]) -> list[Reason]:
    """Return the blocking reasons only, in order."""
    return [r for r in reasons if r.severity is Severity.BLOCKER]
