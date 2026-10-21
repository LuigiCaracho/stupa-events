"""Which actions the actor can try now (a UX hint; the server decides on every write)."""

from __future__ import annotations

from app.modules.pipeline.fieldclass import edit_right
from app.modules.pipeline.snapshot import Actor, Snapshot

OPEN_STATES = frozenset({"idea", "planning", "in_review", "approved"})
REVERTIBLE_STATES = frozenset({"idea", "planning", "live"})
FLYER_STATES = frozenset({"idea", "planning", "in_review"})
VERIFY_STATES = frozenset({"live", "followup", "archived"})
TEMPLATE_STATES = frozenset({"live", "followup", "archived"})
LOCATION_STATES = frozenset({"idea", "planning", "in_review", "approved", "live"})


def allowed_actions(snapshot: Snapshot, actor: Actor) -> list[str]:
    """List the action names (path form) the actor can try on this dossier."""
    live = snapshot.state == "live"
    status = snapshot.public_status
    candidates = (
        ("cancel", live and status != "cancelled" and actor.can("event.cancel")),
        ("postpone", live and status == "scheduled" and actor.can("event.cancel")),
        ("reinstate", live and status != "scheduled" and actor.can("event.approve")),
        (
            "postpone-with-date",
            live
            and status == "scheduled"
            and actor.can("event.cancel")
            and actor.can("event.edit_critical_live"),
        ),
        ("public-text", live and actor.can("event.cancel") and actor.can("event.approve")),
        (
            "image-exception",
            snapshot.state in OPEN_STATES and actor.can("event.image_exception"),
        ),
        (
            "assign-organization",
            snapshot.organization_id is None and actor.can("event.assign_org"),
        ),
        (
            "revert-revision",
            snapshot.state in REVERTIBLE_STATES and actor.can("event.edit_critical_live"),
        ),
        ("acknowledge-changes", live and actor.can("event.edit_critical_live")),
        ("confirm-flyer", snapshot.state in FLYER_STATES and edit_right(snapshot, actor)),
        ("verify-howto", snapshot.state in VERIFY_STATES and actor.can("event.submit")),
        (
            "confirm-location",
            snapshot.state in LOCATION_STATES
            and snapshot.venue_id is None
            and bool((snapshot.venue_text or "").strip())
            and actor.can("event.approve"),
        ),
        (
            "save-as-format",
            snapshot.format_id is None
            and snapshot.organization_id is not None
            and (actor.can("event.submit") or actor.can("format.manage")),
        ),
        ("clone", snapshot.state in TEMPLATE_STATES and actor.can("event.create")),
    )
    return [name for name, ok in candidates if ok]
