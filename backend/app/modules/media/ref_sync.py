"""Keep `media_ref` in step with the images a text refers to.

Saving a text records every image it refers to for its owner. A row is never removed while
the owner lives, because append-only revisions still show the image. Only the draft owner
type is replaced as a set, since a draft is a moving target. The garbage collector sweeps
images without any row.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID, uuid5

from sqlalchemy import delete, select, true
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.models import MarkdownImage, MediaRef
from app.modules.media.refs import image_ids_in

_DRAFT_NAMESPACE = UUID("2b6c1d52-85d1-4f43-8c0e-8f4b9f7a1c33")


def draft_owner_id(document_id: UUID, principal_sub: str) -> UUID:
    """Return the `media_ref` owner id of one person's draft of one document."""
    return uuid5(_DRAFT_NAMESPACE, f"{document_id}:{principal_sub}")


async def _existing(session: AsyncSession, ids: Iterable[UUID]) -> list[UUID]:
    wanted = list(ids)
    if not wanted:
        return []
    return list(await session.scalars(select(MarkdownImage.id).where(MarkdownImage.id.in_(wanted))))


async def add_refs(
    session: AsyncSession, owner_type: str, owner_id: UUID, *texts: str | None
) -> None:
    """Record the images of `texts` for the owner (no commit, nothing is ever removed)."""
    ids = await _existing(session, image_ids_in(*texts))
    if ids:
        await session.execute(
            insert(MediaRef)
            .values([{"image_id": i, "owner_type": owner_type, "owner_id": owner_id} for i in ids])
            .on_conflict_do_nothing()
        )


async def replace_draft_refs(session: AsyncSession, owner_id: UUID, *texts: str | None) -> None:
    """Make the `draft` rows of the owner equal to the images of the current draft."""
    keep = await _existing(session, image_ids_in(*texts))
    await session.execute(
        delete(MediaRef).where(
            MediaRef.owner_type == "draft",
            MediaRef.owner_id == owner_id,
            MediaRef.image_id.not_in(keep) if keep else true(),
        )
    )
    await add_refs(session, "draft", owner_id, *texts)


async def drop_draft_refs(session: AsyncSession, owner_id: UUID) -> None:
    """Remove the draft rows of an owner (draft deleted or purged)."""
    await session.execute(
        delete(MediaRef).where(MediaRef.owner_type == "draft", MediaRef.owner_id == owner_id)
    )
