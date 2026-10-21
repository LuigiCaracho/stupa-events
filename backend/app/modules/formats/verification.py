"""Date a format: `last_verified_at` and the master howto, from a verified edition."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.dossier.models_documents import Document
from app.modules.events.models import Event
from app.modules.formats.models import Format


async def touch_format(session: AsyncSession, format_id: UUID, sub: str, now: datetime) -> None:
    """Date a format and its master howto as verified by `sub` (no commit)."""
    await session.execute(
        update(Format)
        .where(Format.id == format_id)
        .values(last_verified_at=now, last_verified_by=sub)
    )
    await session.execute(
        update(Document)
        .where(Document.format_id == format_id, Document.kind == "howto")
        .values(verified_at=now, verified_by=sub)
    )


async def verify_format(
    session: AsyncSession, principal: Principal, event: Event, now: datetime
) -> None:
    """Date the format of the dossier and its master howto (no commit).

    A no-op without a format, and when the caller holds neither `event.publish` nor
    `format.manage` in the organization of the format: an edition may come from a foreign
    template, and its team must not date a master it does not own.
    """
    if event.format_id is None:
        return
    owner = await session.scalar(select(Format.organization_id).where(Format.id == event.format_id))
    if owner is not None and (
        principal.has("event.publish", owner) or principal.has("format.manage", owner)
    ):
        await touch_format(session, event.format_id, principal.sub, now)
