"""In-app notifications and mails caused by transitions and actions (contract 5.7).

T02 asks the approvers and the editors for a review, T03 tells the owners that changes are
requested (essential, cannot be switched off), every other transition and action tells the
owners that something happened. The acting person never gets a notification of their own
action. The rows share the transaction of the cause; the mails leave after the commit.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal as PrincipalRow
from app.modules.events.models import Event
from app.modules.followup.missing import days_open, missing_of
from app.modules.notifications.service import PendingMail, notify_event
from app.modules.pipeline.snapshot import Snapshot
from app.shared.timeutil import utcnow

_KIND_OF = {"T02": "review_requested", "T03": "changes_requested", "T09b": "auto_archived"}


async def _actor_name(session: AsyncSession, sub: str) -> str:
    name = await session.scalar(select(PrincipalRow.display_name).where(PrincipalRow.sub == sub))
    return name or "Jemand"


async def notice_for(
    session: AsyncSession,
    event: Event,
    step_id: str,
    actor_sub: str,
    *,
    open_comments: int | None = None,
    snapshot: Snapshot | None = None,
) -> tuple[PendingMail, ...]:
    """Notify the people a transition or action concerns; return the mails for after the commit.

    T09b (the system archives a dossier) has its own kind with the open parts of the
    follow-up, read from the snapshot before the transition.
    """
    kind = _KIND_OF.get(step_id, "transition_done")
    params: dict[str, object] = {"actorName": await _actor_name(session, actor_sub)}
    if kind == "changes_requested" and open_comments is not None:
        params["count"] = open_comments
    if kind == "transition_done":
        params["step"] = step_id
    if kind == "auto_archived" and snapshot is not None:
        params |= {
            "daysOpen": days_open(snapshot.entered_followup_at, utcnow()),
            "missing": missing_of(snapshot),
            "howtoUnverified": not snapshot.howto_verified,
        }
    dedupe = f"{kind}:{event.id}:{event.rev}"
    pending = await notify_event(session, kind, event, params, dedupe, actor_sub=actor_sub)
    return tuple(pending)
