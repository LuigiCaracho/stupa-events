"""Who receives a notification kind (contract M4, table 5.7).

`recipients_for` returns the OIDC subs of the people that a kind reaches for a dossier.
Memberships come from the `membership` projection, the editors from the group mappings.
The acting person never receives a notification about their own action; `system:` and
other non-human subs never receive one at all.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Text, Uuid, func, literal, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import column, table

from app.modules.auth.models import Principal
from app.modules.events.models import Event
from app.modules.orgs.models import GroupMapping, Membership
from app.shared.permissions import ORG_ROLES

_COMMENT = table("comment", column("event_id", Uuid), column("author_sub", Text))
_ORGANIZER_ROLES = ("organizer", "approver")
_SYSTEM_PREFIX = "system:"


async def _org_subs(
    session: AsyncSession, org_id: UUID | None, roles: tuple[str, ...]
) -> list[str]:
    if org_id is None:
        return []
    rows = await session.execute(
        select(Principal.sub)
        .join(Membership, Membership.principal_id == Principal.id)
        .where(Membership.organization_id == org_id, Membership.role.in_(roles))
        .where(Principal.active.is_(True))
    )
    return list(rows.scalars())


async def _editor_subs(session: AsyncSession) -> list[str]:
    return await _global_subs(session, ("editor",))


async def _global_subs(session: AsyncSession, roles: tuple[str, ...]) -> list[str]:
    groups = select(GroupMapping.oidc_group).where(
        GroupMapping.role.in_(roles), GroupMapping.organization_id.is_(None)
    )
    names = list((await session.execute(groups)).scalars())
    if not names:
        return []
    rows = await session.execute(
        select(Principal.sub).where(
            func.jsonb_exists_any(Principal.oidc_groups, literal(names, ARRAY(Text))),
            Principal.active.is_(True),
        )
    )
    return list(rows.scalars())


async def _commenter_subs(session: AsyncSession, event: Event) -> list[str]:
    rows = await session.execute(
        select(_COMMENT.c.author_sub).where(_COMMENT.c.event_id == event.id).distinct()
    )
    readers = {
        *_owners(event),
        *await _org_subs(session, event.organization_id, ORG_ROLES),
        *await _global_subs(session, ("editor", "stupa")),
    }
    return [sub for sub in rows.scalars() if sub in readers]


def _owners(event: Event) -> list[str]:
    return [s for s in (event.created_by, event.submitted_by) if s]


def clean(subs: Iterable[str], actor_sub: str | None) -> list[str]:
    """Drop the actor and non-human subs; keep first-seen order without duplicates."""
    return [
        s for s in dict.fromkeys(subs) if s and s != actor_sub and not s.startswith(_SYSTEM_PREFIX)
    ]


async def recipients_for(
    session: AsyncSession, kind: str, event: Event, actor_sub: str | None
) -> list[str]:
    """Return the subs a kind reaches for the dossier, without the acting person.

    Kinds that address one person (`comment_resolved`, `task_assigned`, `checklist_due`)
    are not resolved here: the caller names the recipient.

    Raises:
        KeyError: The kind has no group rule.
    """
    org = event.organization_id
    match kind:
        case "review_requested":
            subs = [*await _org_subs(session, org, ("approver",)), *await _editor_subs(session)]
        case "changes_requested":
            subs = [*_owners(event), *await _org_subs(session, org, ("organizer",))]
        case "comment_added":
            subs = [
                *_owners(event),
                *await _org_subs(session, org, _ORGANIZER_ROLES),
                *await _commenter_subs(session, event),
            ]
        case "transition_done" | "followup_reminder" | "auto_archived":
            subs = [*_owners(event), *await _org_subs(session, org, ("organizer",))]
        case _:
            raise KeyError(kind)
    return clean(subs, actor_sub)
