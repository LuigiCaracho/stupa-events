"""Which dossiers are templates: archived ones everywhere, `published` ones in own scope."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, and_, or_, true

from app.modules.events.models import Event

OWN_CLONABLE = ("published", "archived")


def clonable_clause(scope: set[UUID] | None) -> ColumnElement[bool]:
    """Return the SQL condition of a clonable dossier for a reader with organization `scope`.

    Args:
        scope: The organizations the reader reads (`None` for all), from `readable_org_ids`.
    """
    own = Event.organization_id.in_(scope) if scope is not None else true()
    listed = and_(Event.state == "archived", Event.published_at.is_not(None))
    return or_(listed, and_(Event.state.in_(OWN_CLONABLE), own))


def is_clonable(state: str, own: bool) -> bool:
    """Tell if a dossier in `state` may serve as a template for a reader (`own` scope or not)."""
    return state == "archived" or (own and state in OWN_CLONABLE)
