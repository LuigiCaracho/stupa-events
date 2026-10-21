"""Worker job `promote_poster`: swap the hero of a published dossier to the replacement.

A poster uploaded in `published` waits as an ordinary clean attachment that
supersedes the current hero. Once it is scanned and derived, this job swaps the hero in one
transaction: it hides the old poster, writes a revision ("Poster ersetzt") and raises
`public_seq`. The feed and calendar snapshots are invalidated after the commit.
An infected replacement never gets here, so the old poster stays untouched.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_sessionmaker
from app.modules.audit.actions import AuditAction
from app.modules.events import revisions
from app.modules.events.models import Event
from app.modules.events.postcommit import invalidate_public
from app.modules.files.models import Attachment
from app.shared.timeutil import utcnow

PROMOTE_NOTE = "Poster ersetzt"


async def _swap(session: AsyncSession, new: Attachment) -> Event | None:
    event = await session.scalar(select(Event).where(Event.id == new.event_id).with_for_update())
    if event is None or event.state != "published":
        return None
    if event.hero_attachment_id == new.id:
        return event
    if new.supersedes_id is None or event.hero_attachment_id != new.supersedes_id:
        return None
    old = await session.get(Attachment, new.supersedes_id)
    values: dict[str, Any] = {
        "hero_attachment_id": new.id,
        "rev": Event.rev + 1,
        "public_seq": Event.public_seq + 1,
    }
    result = await session.execute(
        update(Event)
        .where(Event.id == event.id)
        .values(**values)
        .returning(Event)
        .execution_options(populate_existing=True, synchronize_session=False)
    )
    updated = result.scalar_one()
    if old is not None:
        old.retired_at = utcnow()
    await revisions.append_revision(
        session,
        updated,
        actor="system:promote_poster",
        actor_type="system",
        note=PROMOTE_NOTE,
    )
    await revisions.audit(
        session,
        updated,
        actor="system:promote_poster",
        action=AuditAction.ATTACHMENT_REPLACE,
        data={"attachmentId": str(new.id), "promoted": True},
    )
    return updated


async def promote_poster(ctx: dict[str, Any], attachment_id: str) -> str:
    """Promote a clean, derived replacement poster to the hero of its published dossier.

    Returns:
        `"promoted"`, `"skipped"` (nothing to swap yet or any more), or `"gone"`.
    """
    maker = ctx.get("files_sessionmaker") or get_sessionmaker()
    async with maker() as session:
        new = await session.get(Attachment, UUID(attachment_id))
        if new is None:
            return "gone"
        if (
            new.kind != "poster"
            or new.scan_status != "clean"
            or new.retired_at is not None
            or not new.derivatives
        ):
            return "skipped"
        updated = await _swap(session, new)
        if updated is None:
            return "skipped"
        await session.commit()
    await invalidate_public(ctx.get("redis"))
    return "promoted"
