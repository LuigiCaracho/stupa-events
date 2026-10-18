"""Build the `Actor` of a principal for the organization of a dossier."""

from __future__ import annotations

from uuid import UUID

from app.modules.auth.principal import Principal
from app.modules.pipeline.snapshot import Actor, ActorKind
from app.settings import get_settings
from app.shared.permissions import PERMISSION_CATALOGUE


def kind_of(principal: Principal) -> ActorKind:
    """Classify the principal: global `event.approve` is the editor, then admin, else org."""
    if "event.approve" in principal.permissions:
        return "editor"
    return "admin" if principal.is_admin else "org"


def actor_of(
    principal: Principal, org_id: UUID | None, editor_four_eyes: bool | None = None
) -> Actor:
    """Build the actor of a principal for the organization `org_id`.

    The principal must have bound its organization ids (`orgs.scope.bind`).

    Args:
        principal: The resolved principal.
        org_id: Organization of the dossier, `None` for a proposal.
        editor_four_eyes: Whether the Four-Eyes rule binds editors; the setting
            `EDITOR_FOUR_EYES` when omitted.
    """
    kind = kind_of(principal)
    bound = editor_four_eyes if editor_four_eyes is not None else get_settings().editor_four_eyes
    return Actor(
        sub=principal.sub,
        permissions=frozenset(p for p in PERMISSION_CATALOGUE if principal.has(p, org_id)),
        kind=kind,
        four_eyes=kind != "editor" or bound,
    )
