"""Poster upload: the form of the poster route handed to the attachment service.

A poster is the attachment of kind `poster`. `files.attachments.create` sniffs the bytes,
re-encodes the image (bomb guard, no EXIF), stores it in the private bucket and inserts the
row in `pending`; in `draft` it becomes the hero at once, a replacement in `published` waits
for the worker, which swaps it after scan and derivatives. The router commits,
then queues the ClamAV scan.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.principal import Principal
from app.modules.dossier.schemas import PosterMeta
from app.modules.files import attachments
from app.modules.files.attachments import NewAttachment
from app.modules.files.models import Attachment
from app.modules.files.storage import ObjectStorage
from app.shared.errors import PayloadTooLargeError


async def upload_poster(
    session: AsyncSession,
    storage: ObjectStorage | None,
    principal: Principal,
    event_id: UUID,
    *,
    filename: str | None,
    data: bytes,
    meta: PosterMeta,
    max_bytes: int,
) -> Attachment:
    """Store the poster of a dossier (no commit, no scan).

    Raises:
        PayloadTooLargeError: More than `max_bytes` (413).
        NotFoundError, ForbiddenError, ConflictError, UnsupportedMediaTypeError,
        ValidationProblem, ServiceUnavailableError: as `attachments.create`.
    """
    if len(data) > max_bytes:
        raise PayloadTooLargeError(
            f"Poster exceeds {max_bytes} bytes.",
            code="file_too_large",
            extensions={"limitBytes": max_bytes},
        )
    new = NewAttachment(
        kind="poster",
        filename=filename,
        data=data,
        alt_text=meta.alt_text,
        credit=meta.credit,
        rights_basis=meta.rights_basis,
        persons_depicted=meta.persons_depicted,
        consent_note=meta.consent_note,
    )
    return await attachments.create(session, storage, principal, event_id, new)
