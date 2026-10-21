"""In-app notifications and mails of the lifecycle: `published` and `cancelled`.

The people the kind reaches are named in `notifications.recipients`; the acting person never
gets a notification of their own action. The rows share the transaction of the change, the
mails leave after the commit.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal as PrincipalRow
from app.modules.events.models import Event
from app.modules.notifications.service import PendingMail, notify_event

KIND_OF_ACTION = {"publish": "published", "cancel": "cancelled"}


async def _actor_name(session: AsyncSession, sub: str) -> str:
    name = await session.scalar(select(PrincipalRow.display_name).where(PrincipalRow.sub == sub))
    return name or "Jemand"


async def notice_for(
    session: AsyncSession, event: Event, action: str, actor_sub: str
) -> tuple[PendingMail, ...]:
    """Notify the people a lifecycle action concerns; return the mails for after the commit."""
    kind = KIND_OF_ACTION.get(action)
    if kind is None:
        return ()
    params = {"actorName": await _actor_name(session, actor_sub)}
    pending = await notify_event(
        session, kind, event, params, f"{kind}:{event.id}:{event.rev}", actor_sub=actor_sub
    )
    return tuple(pending)
