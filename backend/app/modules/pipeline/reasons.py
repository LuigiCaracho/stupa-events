"""`Reason`: one blocker or warning of a guard, shown before the click (PLAN 4.4)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.shared.errors import ValidationProblem


class Severity(StrEnum):
    """Weight of a reason; only a blocker stops a transition."""

    BLOCKER = "blocker"
    WARNING = "warning"


class FixAction(StrEnum):
    """The one-click remedy the UI offers for a reason."""

    FILL_FIELD = "fill_field"
    CHANGE_DATE = "change_date"
    UPLOAD_POSTER = "upload_poster"
    PICK_VENUE = "pick_venue"
    FILL_RIGHTS = "fill_rights"
    REVIEW_DUPLICATE = "review_duplicate"
    MARK_CANCELLATION = "mark_cancellation"
    OPEN_COMMENT = "open_comment"
    CONFIRM_FLYER = "confirm_flyer"
    CONFIRM_LOCATION = "confirm_location"
    FILL_FACTS = "fill_facts"
    OPEN_CHECKLIST = "open_checklist"
    CONFIRM_TIME = "confirm_time"
    SET_END = "set_end"
    MAKE_OFFER = "make_offer"
    FILL_RETROSPECTIVE = "fill_retrospective"
    FILL_OUTCOME = "fill_outcome"
    VERIFY_HOWTO = "verify_howto"


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


def warning(code: str, *, field: str | None = None, fix: FixAction | None = None) -> Reason:
    """Build a warning with the message key `guards.<code>`; it never stops a transition."""
    return Reason(code, field, Severity.WARNING, f"guards.{code}", fix)


def blockers(reasons: list[Reason]) -> list[Reason]:
    """Return the blocking reasons only, in order."""
    return [r for r in reasons if r.severity is Severity.BLOCKER]


def payload(reasons: list[Reason]) -> list[dict[str, str | None]]:
    """Serialise reasons for the `reasons[]` member of a problem body."""
    return [
        {
            "code": r.code,
            "field": r.field,
            "severity": r.severity.value,
            "messageKey": r.message_key,
            "fixAction": r.fix_action.value if r.fix_action else None,
        }
        for r in reasons
    ]


def refusal(reasons: list[Reason]) -> ValidationProblem:
    """Build the 422 problem for blocking reasons: its code is the first blocker's code."""
    return ValidationProblem(
        "The transition is not allowed yet.",
        code=blockers(reasons)[0].code,
        extensions={"reasons": payload(reasons)},
    )
