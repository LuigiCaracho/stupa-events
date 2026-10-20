"""Who reads an attachment: the visibility table of PLAN 5.4 as pure functions.

`attachment_readable` decides for one attachment, `readable_clause` turns the same decision
into a SQL condition so that lists filter in the database. Quotes, business plans and
contracts ("restricted kinds") additionally need the right to edit the dossier or to read
restricted material, whatever their visibility says. The caller has already established
that the principal reads the dossier at all (404 otherwise).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import ColumnElement, and_, false, or_, true

from app.modules.auth.principal import Principal
from app.modules.files.models import RESTRICTED_KINDS, VISIBILITIES, Attachment


def _sees_team(principal: Principal, org_id: UUID | None) -> bool:
    return principal.has("event.submit", org_id) or principal.has("dossier.read_restricted", org_id)


def restricted_allowed(principal: Principal, org_id: UUID | None) -> bool:
    """Tell if the principal may see quotes, business plans and contracts of the dossier."""
    return (
        principal.has("event.edit", org_id)
        or principal.has("event.read_all", org_id)
        or principal.has("dossier.read_restricted", org_id)
    )


def visibility_readable(principal: Principal, org_id: UUID | None, visibility: str) -> bool:
    """Tell if the principal may see a row of this visibility in a dossier it can read."""
    return _sees_team(principal, org_id) if visibility == "team" else visibility in VISIBILITIES


def attachment_readable(
    principal: Principal, org_id: UUID | None, kind: str, visibility: str
) -> bool:
    """Tell if the principal may see an attachment of a dossier it can read."""
    if kind in RESTRICTED_KINDS and not restricted_allowed(principal, org_id):
        return False
    return visibility_readable(principal, org_id, visibility)


def readable_clause(principal: Principal, org_id: UUID | None) -> ColumnElement[bool]:
    """Return the SQL condition that selects exactly the readable attachments."""
    visible = [v for v in VISIBILITIES if attachment_readable(principal, org_id, "other", v)]
    by_visibility = Attachment.visibility.in_(visible) if visible else false()
    restricted = true() if restricted_allowed(principal, org_id) else false()
    return and_(by_visibility, or_(restricted, Attachment.kind.not_in(RESTRICTED_KINDS)))
