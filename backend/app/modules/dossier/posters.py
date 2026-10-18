"""Poster upload: sniff, re-encode, store, link to the dossier (no commit, no scan).

The upload sniffs the MIME type (JPEG, PNG, WebP only), decodes and encodes the image
again with Pillow (bomb guard, no EXIF), stores the bytes in the private bucket and
inserts an attachment in `pending`. The earlier poster stays and is retired through
`supersedes_id`. The router commits, then queues the ClamAV scan; the worker derives the
public WebP variants after a clean scan.
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import threading
import uuid
from typing import Final
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.dossier.schemas import PosterMeta
from app.modules.events import revisions
from app.modules.events.access import load_visible, poster_of
from app.modules.events.models import Event
from app.modules.events.states import EventState
from app.modules.files.mime import MimeRejected, validate_upload
from app.modules.files.models import Attachment
from app.modules.files.storage import ObjectStorage, StorageError
from app.modules.media.images import CleanImage, ImageRejected, clean_image
from app.modules.media.models import POSTER_MIMES
from app.modules.orgs.scope import bind, restricted_to_own
from app.shared.errors import (
    ConflictError,
    ForbiddenError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    UnsupportedMediaTypeError,
)
from app.shared.filenames import sanitize_display_name, sanitize_storage_name
from app.shared.timeutil import utcnow

CLEAN_CONCURRENCY: Final[int] = 2
_clean_threads: Final = threading.BoundedSemaphore(CLEAN_CONCURRENCY)
_clean_slots: Final = asyncio.Semaphore(CLEAN_CONCURRENCY)
_EDIT_STATES = frozenset({EventState.IDEA.value, EventState.PLANNING.value})


def _clean_bounded(data: bytes) -> CleanImage:
    with _clean_threads:
        return clean_image(data, POSTER_MIMES)


def authorize_upload(principal: Principal, event: Event) -> None:
    """Check the right to attach a poster in the current state.

    `idea` and `planning`: the creator (submitter) or any role with `dossier.attach` in
    the organization. `in_review`: approvers and editors only. Later: locked.
    """
    org_id = event.organization_id
    if org_id is None or not principal.has("dossier.attach", org_id):
        raise ForbiddenError("Missing permission: dossier.attach")
    if event.state in _EDIT_STATES:
        if restricted_to_own(principal, org_id) and event.created_by != principal.sub:
            raise ForbiddenError("Only the creator may attach to this dossier.")
    elif event.state == EventState.IN_REVIEW.value:
        if not principal.has("event.approve", org_id):
            raise ForbiddenError("Only approvers may replace the poster during review.")
    else:
        raise ConflictError("Field is locked in this state.", code="field_locked")


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
    """Store the poster and make it the hero of the dossier (no commit).

    Raises:
        NotFoundError: No read right on the event.
        ForbiddenError, ConflictError: The right or the state forbids the upload.
        ServiceUnavailableError: The object storage is off or failed (503).
        PayloadTooLargeError: More than `max_bytes` (413).
        UnsupportedMediaTypeError: Not a JPEG, PNG or WebP image (415).
    """
    event = await load_visible(session, principal, event_id)
    await bind(session, principal)
    authorize_upload(principal, event)
    if storage is None:
        raise ServiceUnavailableError("Object storage unavailable.")
    if len(data) > max_bytes:
        raise PayloadTooLargeError(f"Poster exceeds {max_bytes} bytes.")
    try:
        validate_upload(filename, data, POSTER_MIMES)
        async with _clean_slots:
            image = await asyncio.to_thread(_clean_bounded, data)
    except (MimeRejected, ImageRejected) as exc:
        raise UnsupportedMediaTypeError(str(exc)) from exc
    if len(image.data) > max_bytes:
        raise PayloadTooLargeError(f"Poster exceeds {max_bytes} bytes.")

    previous = await poster_of(session, event)
    attachment_id = uuid.uuid4()
    row = Attachment(
        id=attachment_id,
        event_id=event.id,
        kind="poster",
        storage_key=f"events/{event.id}/poster/{attachment_id}",
        display_name=sanitize_display_name(filename),
        storage_name=sanitize_storage_name(filename),
        mime=image.mime,
        size_bytes=len(image.data),
        sha256=hashlib.sha256(image.data).hexdigest(),
        alt_text=meta.alt_text,
        credit=meta.credit,
        rights_basis=meta.rights_basis,
        supersedes_id=previous.id if previous else None,
    )
    session.add(row)
    await session.flush()
    try:
        assert row.storage_key is not None
        await storage.put(row.storage_key, image.data, image.mime)
    except StorageError as exc:
        raise ServiceUnavailableError("Object storage write failed.") from exc
    try:
        if previous is not None:
            previous.retired_at = utcnow()
        updated = await _link_hero(session, event, attachment_id)
        await revisions.append_revision(
            session, updated, actor=principal.sub, field_class="dossier"
        )
        await revisions.audit(
            session,
            updated,
            actor=principal.sub,
            action=AuditAction.ATTACHMENT_REPLACE if previous else AuditAction.ATTACHMENT_UPLOAD,
            data={"attachmentId": str(attachment_id)},
        )
    except BaseException:
        with contextlib.suppress(StorageError):
            await storage.remove(row.storage_key)
        raise
    return row


async def _link_hero(session: AsyncSession, event: Event, attachment_id: UUID) -> Event:
    result = await session.execute(
        update(Event)
        .where(Event.id == event.id, Event.rev == event.rev)
        .values(hero_attachment_id=attachment_id, rev=Event.rev + 1)
        .returning(Event)
        .execution_options(populate_existing=True, synchronize_session=False)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("The dossier was changed in the meantime.")
    return updated
