"""Run an action that returns a `Fired`: present the dossier, commit, then the follow-ups."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.events.conflict import set_etag, with_current
from app.modules.events.postcommit import run_actions
from app.modules.events.presenter import present
from app.modules.events.schemas import EventOut
from app.modules.events.step import Fired
from app.modules.notifications.service import dispatch_mails


async def respond(
    request: Request,
    db: AsyncSession,
    principal: Principal,
    response: Response,
    work: Callable[[], Awaitable[Fired]],
) -> EventOut:
    """Do the work, present the changed dossier, commit and run the actions and mails."""
    async with with_current(db, principal):
        fired = await work()
    out = (await present(db, principal, [fired.event]))[0]
    out.checklist_recomputed = db.info.pop("checklist_recomputed", None)
    out.facts_dropped = db.info.pop("facts_dropped", None)
    await db.commit()
    set_etag(response, out.rev)
    pool = getattr(request.app.state, "arq_pool", None)
    await run_actions(pool, fired.actions, fired.committed)
    await dispatch_mails(pool, fired.mails)
    return out
