"""The expected decision of every transition, written from PLAN 4.3 and the contract table.

This file does not import `TRANSITIONS`: it is the independent second source that the
matrix test compares the product against. A cell is `(state, transition, who, poster,
eyes, clock, note)`; the answer is the outcome word of `decide`.
"""

from __future__ import annotations

SOURCES: dict[str, tuple[set[str], str]] = {
    "T01": ({"idea"}, "planning"),
    "T02": ({"planning"}, "in_review"),
    "T03": ({"in_review"}, "planning"),
    "T04": ({"in_review"}, "approved"),
    "T05": ({"approved"}, "live"),
    "T06": ({"approved"}, "in_review"),
    "T07": ({"live"}, "approved"),
    "T08": ({"live"}, "followup"),
    "T08b": ({"live"}, "archived"),
    "T09": ({"followup"}, "archived"),
    "T09b": ({"followup"}, "archived"),
    "T10": ({"archived"}, "followup"),
    "T11": ({"idea", "planning", "in_review", "approved"}, "withdrawn"),
    "T12": ({"withdrawn"}, "idea"),
}
WHO = (
    "viewer",
    "member",
    "submitter_own",
    "submitter_foreign",
    "organizer",
    "approver",
    "editor",
    "admin",
    "stupa",
    "system",
)
_STAFF = {"organizer", "approver", "editor", "admin"}
_APPROVERS = {"approver", "editor", "admin"}
_EDITORS = {"editor", "admin"}
RIGHT: dict[str, set[str]] = {
    "T01": {"submitter_own"} | _STAFF,
    "T02": _STAFF,
    "T03": _APPROVERS,
    "T04": _APPROVERS,
    "T05": _APPROVERS | {"system"},
    "T06": _APPROVERS,
    "T07": _APPROVERS,
    "T08": {"system"},
    "T08b": {"system"},
    "T09": _STAFF,
    "T09b": {"system"},
    "T10": _EDITORS,
    "T11": _STAFF,
    "T12": _EDITORS,
}
NOTE_REQUIRED = {"T03", "T06", "T07", "T10", "T11"}
FOUR_EYES_BOUND = {"approver", "admin"}


def _has_right(tid: str, who: str, state: str) -> bool:
    if tid == "T11" and who == "submitter_own":
        return state == "idea"
    return who in RIGHT[tid]


def _blocked(tid: str, who: str, poster: str, clock: str) -> bool:
    no_image = poster == "missing"
    past = clock == "past"
    match tid:
        case "T02":
            return past
        case "T04":
            return past or no_image
        case "T05":
            return no_image or (who == "system" and past)
        case "T08" | "T08b":
            return clock == "running"
        case _:
            return False


def expected(tid: str, state: str, who: str, poster: str, eyes: str, clock: str, note: bool) -> str:
    """Return the outcome word the product must produce for this cell."""
    sources, _target = SOURCES[tid]
    if not _has_right(tid, who, state):
        return "forbidden"
    if state not in sources:
        return "invalid_transition"
    if tid in NOTE_REQUIRED and not note:
        return "reason_required"
    if tid == "T04" and (who in FOUR_EYES_BOUND) and eyes != "other":
        return "four_eyes"
    return "blocked" if _blocked(tid, who, poster, clock) else "ok"
