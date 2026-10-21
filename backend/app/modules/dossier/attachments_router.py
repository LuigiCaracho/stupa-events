"""Attachment routes: list, upload, change, replace, hide, rescan, download and preview."""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse

from app.deps import DbSession, Principal, require_any_scope, require_principal
from app.modules.dossier.counts import DossierCounts, dossier_counts
from app.modules.dossier.deps import AttachmentStorage, ScanQueueDep
from app.modules.dossier.schemas import (
    AttachmentKind,
    AttachmentOut,
    AttachmentPatch,
    RightsBasis,
    Visibility,
    attachment_out,
)
from app.modules.events.postcommit import invalidate_public
from app.modules.files import attachments
from app.modules.files.attachment_types import MAX_DOCUMENT_BYTES
from app.modules.files.attachments import NewAttachment
from app.modules.files.storage import ObjectStorage, StorageError
from app.shared.antiabuse import rate_limit_attachments
from app.shared.errors import (
    ConflictError,
    GoneError,
    NotFoundError,
    PayloadTooLargeError,
    ProblemDetail,
    ServiceUnavailableError,
    ValidationProblem,
)
from app.shared.filenames import content_disposition

router = APIRouter(tags=["attachments"])
logger = logging.getLogger("app.files")

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    c: _PROBLEM for c in (401, 403, 404, 409, 410, 413, 415, 422, 503)
}
_FRAME_BYTES = 256 * 1024

Attacher = Annotated[Principal, Depends(require_any_scope("dossier.attach"))]
Reader = Annotated[Principal, Depends(require_principal("library.read"))]
Approver = Annotated[Principal, Depends(require_any_scope("event.publish"))]


def enforce_upload_cap(request: Request) -> None:
    """Answer 413 when the `Content-Length` of an upload clearly exceeds 25 MiB."""
    raw = request.headers.get("content-length")
    if raw is not None and raw.isdigit() and int(raw) > MAX_DOCUMENT_BYTES + _FRAME_BYTES:
        raise PayloadTooLargeError(
            "Request body is too large.",
            code="file_too_large",
            extensions={"limitBytes": MAX_DOCUMENT_BYTES},
        )


UploadGuards = [Depends(enforce_upload_cap), Depends(rate_limit_attachments)]


def _meta(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationProblem("meta must be JSON text.") from exc
    if not isinstance(value, dict):
        raise ValidationProblem("meta must be a JSON object.")
    return value


async def _new(
    file: UploadFile,
    kind: str,
    form: dict[str, Any],
) -> NewAttachment:
    data = await file.read(MAX_DOCUMENT_BYTES + 1)
    return NewAttachment(
        kind=kind,
        filename=file.filename,
        data=data,
        meta=_meta(form.pop("meta")),
        **{k: v for k, v in form.items() if v is not None},
    )


async def _enqueue_scan(queue: ScanQueueDep, attachment_id: UUID) -> None:
    if queue is None:
        return
    try:
        await queue.enqueue(attachment_id)
    except Exception:  # noqa: BLE001 - the row is committed, the stale-scan cron requeues it
        logger.warning("scan enqueue failed (attachment=%s)", attachment_id, exc_info=True)


async def _commit_and_scan(
    db: DbSession, storage: ObjectStorage | None, queue: ScanQueueDep, row: Any
) -> None:
    out_key = row.storage_key
    try:
        await db.commit()
    except BaseException:
        if storage is not None and out_key is not None:
            with contextlib.suppress(StorageError):
                await storage.remove(out_key)
        raise
    await _enqueue_scan(queue, row.id)


@router.get("/events/{event_id}/attachments", response_model=list[AttachmentOut], responses=_ERRORS)
async def list_attachments(
    db: DbSession,
    principal: Reader,
    event_id: UUID,
    kind: Annotated[AttachmentKind | None, Query()] = None,
    include_retired: Annotated[bool, Query(alias="includeRetired")] = False,
) -> list[AttachmentOut]:
    """List the attachments of a dossier that the caller may see, filtered in SQL."""
    rows = await attachments.list_attachments(
        db, principal, event_id, kind=kind, include_retired=include_retired
    )
    return [attachment_out(row, successor) for row, successor in rows]


@router.post(
    "/events/{event_id}/attachments",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=UploadGuards,
    responses=_ERRORS,
)
async def upload_attachment(
    db: DbSession,
    storage: AttachmentStorage,
    queue: ScanQueueDep,
    principal: Attacher,
    event_id: UUID,
    file: Annotated[UploadFile, File()],
    kind: Annotated[AttachmentKind, Form()],
    visibility: Annotated[Visibility | None, Form()] = None,
    alt_text: Annotated[str | None, Form(alias="altText")] = None,
    credit: Annotated[str | None, Form()] = None,
    rights_basis: Annotated[RightsBasis, Form(alias="rightsBasis")] = "unknown",
    license_ref: Annotated[str | None, Form(alias="licenseRef")] = None,
    source_url: Annotated[str | None, Form(alias="sourceUrl")] = None,
    persons_depicted: Annotated[bool, Form(alias="personsDepicted")] = False,
    consent_note: Annotated[str | None, Form(alias="consentNote")] = None,
    contains_date: Annotated[bool, Form(alias="containsDate")] = False,
    dated_for: Annotated[date | None, Form(alias="datedFor")] = None,
    meta: Annotated[str | None, Form()] = None,
) -> AttachmentOut:
    """Upload a file of any kind; it starts in `pending` until ClamAV has scanned it."""
    new = await _new(
        file,
        kind,
        {
            "visibility": visibility,
            "alt_text": alt_text,
            "credit": credit,
            "rights_basis": rights_basis,
            "license_ref": license_ref,
            "source_url": source_url,
            "persons_depicted": persons_depicted,
            "consent_note": consent_note,
            "contains_date": contains_date,
            "dated_for": dated_for,
            "meta": meta,
        },
    )
    row = await attachments.create(db, storage, principal, event_id, new)
    out = attachment_out(row)
    await _commit_and_scan(db, storage, queue, row)
    return out


@router.patch("/attachments/{attachment_id}", response_model=AttachmentOut, responses=_ERRORS)
async def patch_attachment(
    request: Request,
    db: DbSession,
    principal: Attacher,
    attachment_id: UUID,
    body: AttachmentPatch,
) -> AttachmentOut:
    """Change visibility, name, rights fields or meta (the last writer wins)."""
    row = await attachments.patch(db, principal, attachment_id, body.model_dump(exclude_unset=True))
    out = attachment_out(row)
    await db.commit()
    if row.kind == "poster":
        await invalidate_public(getattr(request.app.state, "arq_pool", None))
    return out


@router.post(
    "/attachments/{attachment_id}/replace",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=UploadGuards,
    responses=_ERRORS,
)
async def replace_attachment(
    db: DbSession,
    storage: AttachmentStorage,
    queue: ScanQueueDep,
    principal: Attacher,
    attachment_id: UUID,
    file: Annotated[UploadFile, File()],
    visibility: Annotated[Visibility | None, Form()] = None,
    alt_text: Annotated[str | None, Form(alias="altText")] = None,
    credit: Annotated[str | None, Form()] = None,
    rights_basis: Annotated[RightsBasis, Form(alias="rightsBasis")] = "unknown",
    license_ref: Annotated[str | None, Form(alias="licenseRef")] = None,
    source_url: Annotated[str | None, Form(alias="sourceUrl")] = None,
    persons_depicted: Annotated[bool | None, Form(alias="personsDepicted")] = None,
    consent_note: Annotated[str | None, Form(alias="consentNote")] = None,
    contains_date: Annotated[bool, Form(alias="containsDate")] = False,
    dated_for: Annotated[date | None, Form(alias="datedFor")] = None,
    meta: Annotated[str | None, Form()] = None,
) -> AttachmentOut:
    """Upload a new version of an attachment; its metadata carries over unless resent."""
    new = await _new(
        file,
        "other",
        {
            "visibility": visibility,
            "alt_text": alt_text,
            "credit": credit,
            "rights_basis": rights_basis,
            "license_ref": license_ref,
            "source_url": source_url,
            "persons_depicted": persons_depicted,
            "consent_note": consent_note,
            "contains_date": contains_date,
            "dated_for": dated_for,
            "meta": meta,
        },
    )
    row = await attachments.replace(db, storage, principal, attachment_id, new)
    out = attachment_out(row)
    await _commit_and_scan(db, storage, queue, row)
    return out


@router.post(
    "/attachments/{attachment_id}/retire",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=_ERRORS,
)
async def retire_attachment(
    request: Request, db: DbSession, principal: Attacher, attachment_id: UUID
) -> Response:
    """Hide an attachment; there is no delete."""
    kind = await attachments.retire(db, principal, attachment_id)
    await db.commit()
    if kind == "poster":
        await invalidate_public(getattr(request.app.state, "arq_pool", None))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/attachments/{attachment_id}/rescan",
    status_code=status.HTTP_202_ACCEPTED,
    responses=_ERRORS,
)
async def rescan_attachment(
    db: DbSession, queue: ScanQueueDep, principal: Approver, attachment_id: UUID
) -> Response:
    """Queue a new scan of an attachment whose scan failed or never started."""
    row = await attachments.request_rescan(db, principal, attachment_id)
    await db.commit()
    await _enqueue_scan(queue, row.id)
    return Response(status_code=status.HTTP_202_ACCEPTED)


def _check_scanned(scan_status: str) -> None:
    if scan_status == "infected":
        raise GoneError("The file was infected and removed.", code="attachment_infected")
    if scan_status != "clean":
        raise ConflictError("The file is in quarantine until it is scanned.", code="quarantined")


async def _chunks(storage: ObjectStorage, key: str) -> AsyncIterator[bytes]:
    try:
        async for chunk in await storage.get_stream(key):
            yield chunk
    except StorageError as exc:
        raise ServiceUnavailableError("File temporarily unavailable.") from exc


@router.get("/attachments/{attachment_id}/download", responses=_ERRORS, response_class=Response)
async def download_attachment(
    db: DbSession, storage: AttachmentStorage, principal: Reader, attachment_id: UUID
) -> Response:
    """Stream the file as a download; only clean files leave the quarantine."""
    row, _ = await attachments.load_attachment(db, principal, attachment_id, archive=True)
    _check_scanned(row.scan_status)
    if storage is None or row.storage_key is None:
        raise ServiceUnavailableError("Object storage unavailable.")
    try:
        stream = await storage.get_stream(row.storage_key)
    except StorageError as exc:
        raise ServiceUnavailableError("File temporarily unavailable.") from exc
    return StreamingResponse(
        stream,
        media_type=row.mime,
        headers={
            "Content-Disposition": content_disposition("attachment", row.display_name),
            "Content-Length": str(row.size_bytes),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/attachments/{attachment_id}/preview", responses=_ERRORS, response_class=Response)
async def preview_attachment(
    db: DbSession, storage: AttachmentStorage, principal: Reader, attachment_id: UUID
) -> Response:
    """Return the private WebP preview of an image, inline."""
    row, _ = await attachments.load_attachment(db, principal, attachment_id, archive=True)
    _check_scanned(row.scan_status)
    if row.preview_key is None:
        raise NotFoundError("no preview")
    if storage is None:
        raise ServiceUnavailableError("Object storage unavailable.")
    try:
        body = await storage.get(row.preview_key)
    except StorageError as exc:
        raise ServiceUnavailableError("Preview temporarily unavailable.") from exc
    return Response(
        body,
        media_type="image/webp",
        headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"},
    )


@router.get(
    "/events/{event_id}/dossier-counts",
    response_model=DossierCounts,
    response_model_exclude_none=True,
    responses=_ERRORS,
)
async def get_dossier_counts(db: DbSession, principal: Reader, event_id: UUID) -> DossierCounts:
    """Return the tab counters; restricted counters appear only for those who may see them."""
    return await dossier_counts(db, principal, event_id)
