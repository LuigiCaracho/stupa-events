"""Which actions the caller can try on a dossier now (a hint; the server decides on a write)."""

from __future__ import annotations

from app.modules.auth.principal import Principal
from app.modules.events.editing import may_edit
from app.modules.events.lifecycle import EDITOR_RIGHT
from app.modules.events.models import Event
from app.modules.events.states import EventState

VERIFY_STATES = frozenset({EventState.PUBLISHED, EventState.ARCHIVED})
TEMPLATE_STATES = frozenset({EventState.PUBLISHED, EventState.ARCHIVED})
LOCATION_STATES = frozenset({EventState.DRAFT, EventState.PUBLISHED})


def allowed_actions(
    principal: Principal, event: Event, *, requires_editor: bool = False
) -> list[str]:
    """List the action names (path form) the caller can try on this dossier.

    The principal must have bound its organization ids (`orgs.scope.bind`).
    """
    org = event.organization_id
    state, status = event.state, event.public_status
    can_publish = principal.has("event.publish", org)
    may_cancel = state == EventState.PUBLISHED and principal.has("event.cancel", org)
    free_venue = event.venue_id is None and bool((event.venue_text or "").strip())
    candidates = (
        (
            "publish",
            state == EventState.DRAFT
            and can_publish
            and (not requires_editor or principal.has(EDITOR_RIGHT, org)),
        ),
        ("unpublish", state == EventState.PUBLISHED and can_publish),
        ("archive", state in (EventState.DRAFT, EventState.PUBLISHED) and can_publish),
        ("restore", state == EventState.ARCHIVED and principal.has("event.restore", org)),
        ("cancel", may_cancel and status != "cancelled"),
        ("postpone", may_cancel and status == "scheduled"),
        ("reinstate", may_cancel and status != "scheduled"),
        ("revert-revision", may_edit(principal, event)),
        ("confirm-location", state in LOCATION_STATES and free_venue and can_publish),
        ("verify-howto", state in VERIFY_STATES and can_publish),
        (
            "save-as-format",
            event.format_id is None
            and org is not None
            and (can_publish or principal.has("format.manage")),
        ),
        ("clone", state in TEMPLATE_STATES and principal.has("event.create", org)),
    )
    return [name for name, ok in candidates if ok]
