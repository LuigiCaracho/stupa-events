"""Who may change the base data of a dossier, in which state, as pure functions.

The base data are the fields of `DraftFields` and the facts. They are editable in `draft`
with `event.edit` (a submitter only on its own dossiers), in `published` with `event.publish`
and not in `archived` (restore first). A change of a field that the public sees raises
`public_seq` while the dossier is published.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.modules.auth.principal import Principal
from app.modules.events.models import Event
from app.modules.events.states import EventState
from app.modules.orgs.scope import restricted_to_own
from app.shared.errors import ConflictError, FieldError

API_NAMES: dict[str, str] = {
    "title": "title",
    "starts_at": "startsAt",
    "ends_at": "endsAt",
    "all_day": "allDay",
    "starts_on": "startsOn",
    "ends_on": "endsOn",
    "venue_id": "venueId",
    "venue_text": "venueText",
    "primary_category_id": "primaryCategoryId",
    "ticket_url": "ticketUrl",
    "website_url": "websiteUrl",
    "summary": "summary",
    "description_md": "descriptionMd",
    "cost_text": "costText",
}
PUBLIC_FIELDS: frozenset[str] = frozenset(
    {
        "title",
        "starts_at",
        "ends_at",
        "all_day",
        "starts_on",
        "ends_on",
        "venue_id",
        "venue_text",
        "primary_category_id",
        "ticket_url",
        "website_url",
        "summary",
    }
)


def has_edit_right(principal: Principal, event: Event) -> bool:
    """Tell if the principal holds the right to edit this dossier, whatever its state.

    A published dossier asks for `event.publish`; any other state for `event.edit`, and a
    submitter edits only its own dossiers. The principal must have bound its organization
    ids (`orgs.scope.bind`).
    """
    org = event.organization_id
    if event.state == EventState.PUBLISHED:
        return principal.has("event.publish", org)
    if not principal.has("event.edit", org):
        return False
    return not restricted_to_own(principal, org) or event.created_by == principal.sub


def may_edit(principal: Principal, event: Event) -> bool:
    """Tell if the principal may change the base data of this dossier now."""
    return event.state != EventState.ARCHIVED and has_edit_right(principal, event)


def editable_fields(principal: Principal, event: Event) -> list[str]:
    """List the API names of the fields the principal may change now (a UX hint only)."""
    return list(API_NAMES.values()) if may_edit(principal, event) else []


def bumps_public_seq(event: Event, changes: Mapping[str, Any]) -> bool:
    """Tell if a change of a published dossier alters what the public sees."""
    return event.state == EventState.PUBLISHED and bool(PUBLIC_FIELDS & changes.keys())


def locked_problem(fields: tuple[str, ...]) -> ConflictError:
    """Build the 409 `field_locked` problem naming every locked field."""
    return ConflictError(
        "Field is locked in this state.",
        code="field_locked",
        errors=[FieldError(field=f, msg="locked in this state") for f in fields],
    )
