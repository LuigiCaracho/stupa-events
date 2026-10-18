"""Field classes (E07): which fields a person may change in which state, as a pure function.

`plan_patch` takes the dossier snapshot, the actor and the requested changes (column
names) and returns a `PatchPlan`: the effective changes, the fields the state or the right
locks, the revision class and whether `public_seq` rises. It knows neither the database nor
the session. A request is all or nothing: one locked field locks the whole request.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.events.states import EventState as S
from app.modules.pipeline.snapshot import Actor, Snapshot

CRITICAL_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "starts_at",
        "ends_at",
        "all_day",
        "venue_id",
        "venue_text",
        "primary_category_id",
        "ticket_url",
        "website_url",
    }
)
TEXT_FIELDS: frozenset[str] = frozenset({"summary", "description_md", "cost_text"})
GUARDED_TEXT: frozenset[str] = frozenset({"summary"})
API_NAMES: dict[str, str] = {
    "title": "title",
    "starts_at": "startsAt",
    "ends_at": "endsAt",
    "all_day": "allDay",
    "venue_id": "venueId",
    "venue_text": "venueText",
    "primary_category_id": "primaryCategoryId",
    "ticket_url": "ticketUrl",
    "website_url": "websiteUrl",
    "summary": "summary",
    "description_md": "descriptionMd",
    "cost_text": "costText",
}
type LockReason = Literal["in_review", "approved", "live_critical", "closed"]
_OPEN = {S.IDEA.value, S.PLANNING.value}
_CLOSED = {S.FOLLOWUP.value, S.ARCHIVED.value, S.WITHDRAWN.value}
_HOST = re.compile(
    r"(?:\b[a-z][a-z0-9+.-]*://|(?<![:\w])//|(?<![@\w.])(?=www\.))"
    r"(?P<host>[^\s/?#<>\"'()\[\]\\]+)",
    re.IGNORECASE,
)
_BARE = re.compile(
    r"(?<![@\w./-])(?P<host>(?:[a-z0-9-]+\.)+(?:[a-z]{2,24}|xn--[a-z0-9-]+))"
    r"(?![\w@-])(?=\.?(?:[/:?#\s)\]>\"']|$))",
    re.IGNORECASE,
)


def link_hosts(text: str | None) -> frozenset[str]:
    """Return the normalised hosts of the links in `text`.

    Counted: any `scheme://host`, protocol-relative `//host`, `www.` and bare `domain.tld`
    (also with a path or port). The M5 sanitizer must drop everything else that can carry
    a target (`javascript:`, `data:`), so this stays the complete list of hosts.
    """
    found: set[str] = set()
    matches = [*_HOST.finditer(text or ""), *_BARE.finditer(text or "")]
    for match in matches:
        host = match["host"].rsplit("@", 1)[-1].split(":", 1)[0].strip(".,;!").lower()
        if not host:
            continue
        with contextlib.suppress(UnicodeError):
            host = host.encode("idna").decode("ascii")
        found.add(host)
    return frozenset(found)


def known_hosts(snapshot: Snapshot) -> frozenset[str]:
    """Return the hosts that the dossier already links to."""
    texts = (
        snapshot.summary,
        snapshot.description_md,
        snapshot.cost_text,
        snapshot.ticket_url,
        snapshot.website_url,
    )
    return frozenset().union(*(link_hosts(text) for text in texts))


@dataclass(frozen=True, slots=True)
class PatchPlan:
    """What a `PATCH` does: effective changes, locked fields and the revision class."""

    changes: Mapping[str, Any]
    locked: tuple[str, ...]
    field_class: Literal["critical", "text"]
    bump_public_seq: bool
    live_guards: bool


def edit_right(snapshot: Snapshot, actor: Actor) -> bool:
    """Tell if the actor may edit this dossier at all (before any state lock).

    A dossier without an organization (a proposal) is edited by a global `event.edit`
    only. A role without `event.submit` edits its own dossiers in `idea` and `planning`.
    """
    if not actor.can("event.edit"):
        return False
    if actor.can("event.submit"):
        return True
    return snapshot.created_by == actor.sub and snapshot.state in _OPEN


def _critical_locked(snapshot: Snapshot, actor: Actor) -> bool:
    if snapshot.state in _OPEN:
        return False
    return not (snapshot.state == S.LIVE.value and actor.can("event.edit_critical_live"))


def _text_locked(snapshot: Snapshot, actor: Actor) -> bool:
    if snapshot.state in _OPEN or snapshot.state == S.LIVE.value:
        return False
    return not (snapshot.state == S.IN_REVIEW.value and actor.can("event.approve"))


def lock_reason(snapshot: Snapshot, actor: Actor) -> LockReason | None:
    """Return why critical fields are locked for this actor, `None` when they are not."""
    if snapshot.state in _CLOSED:
        return "closed"
    if snapshot.state == S.APPROVED.value:
        return "approved"
    if snapshot.state == S.IN_REVIEW.value:
        return "in_review"
    return "live_critical" if _critical_locked(snapshot, actor) else None


def editable_fields(snapshot: Snapshot, actor: Actor) -> list[str]:
    """List the API names of the fields the actor may change now (UX hint only)."""
    if not edit_right(snapshot, actor):
        return []
    critical, text = not _critical_locked(snapshot, actor), not _text_locked(snapshot, actor)
    return [
        API_NAMES[name]
        for name in API_NAMES
        if name != "all_day" and (critical if name in CRITICAL_FIELDS else text)
    ]


def _effective(snapshot: Snapshot, changes: Mapping[str, Any]) -> dict[str, Any]:
    return {name: value for name, value in changes.items() if getattr(snapshot, name) != value}


def _classes(snapshot: Snapshot, changes: Mapping[str, Any]) -> dict[str, str]:
    known = known_hosts(snapshot)
    return {
        name: "critical" if name in CRITICAL_FIELDS or (link_hosts(value) - known) else "text"
        for name, value in changes.items()
    }


def plan_patch(snapshot: Snapshot, actor: Actor, changes: Mapping[str, Any]) -> PatchPlan:
    """Plan a change of fields: classify them and lock by state and right.

    Args:
        snapshot: The dossier before the change.
        actor: Who changes it.
        changes: Requested column values; values equal to the current ones are ignored.

    Returns:
        The plan. `locked` names (API names) every field that the state or the actor's
        rights lock; the caller must refuse the whole request when it is not empty.
    """
    effective = _effective(snapshot, changes)
    classes = _classes(snapshot, effective)
    blocked = {"critical": _critical_locked(snapshot, actor), "text": _text_locked(snapshot, actor)}
    locked = tuple(API_NAMES[name] for name, kind in classes.items() if blocked[kind])
    critical = "critical" in classes.values()
    live = snapshot.state == S.LIVE.value
    return PatchPlan(
        changes=effective,
        locked=locked,
        field_class="critical" if critical else "text",
        bump_public_seq=live and (critical or "summary" in effective),
        live_guards=live and (critical or bool(GUARDED_TEXT & effective.keys())),
    )
