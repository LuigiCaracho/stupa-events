"""Poster endpoints of a dossier: upload and the internal derivative download."""

from __future__ import annotations

import contextlib
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from pydantic import ValidationError

from app.deps import DbSession, Principal, SettingsDep, require_any_scope, require_principal
from app.modules.dossier import posters
from app.modules.dossier.deps import AttachmentStorage, PublicStorage, ScanQueueDep
from app.modules.dossier.schemas import (
    VARIANT_KEYS,
    AttachmentOut,
    PosterMeta,
    PosterVariant,
    attachment_out,
)
from app.modules.events.access import load_visible, poster_of
from app.modules.files.storage import StorageError
from app.shared.antiabuse import enforce_attachment_body_cap, rate_limit_attachments
from app.shared.errors import (
    ConflictError,
    FieldError,
    NotFoundError,
    ProblemDetail,
    ServiceUnavailableError,
    ValidationProblem,
)

router = APIRouter(prefix="/events", tags=["dossier"])

_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: _PROBLEM,
    403: _PROBLEM,
    404: _PROBLEM,
    409: _PROBLEM,
    413: _PROBLEM,
    415: _PROBLEM,
    422: _PROBLEM,
    503: _PROBLEM,
}


async def _read_capped(file: UploadFile, max_bytes: int) -> bytes:
    """Read at most `max_bytes + 1` bytes, so an oversize file is seen but never buffered."""
    return await file.read(max_bytes + 1)


def _meta(
    alt_text: str,
    credit: str,
    rights_basis: str,
    persons_depicted: bool,
    consent_note: str | None,
) -> PosterMeta:
    try:
        return PosterMeta.model_validate(
            {
                "altText": alt_text,
                "credit": credit,
                "rightsBasis": rights_basis,
                "personsDepicted": persons_depicted,
                "consentNote": consent_note,
            }
        )
    except ValidationError as exc:
        raise ValidationProblem(
            "Invalid poster metadata.",
            errors=[FieldError(field=str(e["loc"][0]), msg=e["msg"]) for e in exc.errors()],
        ) from exc


@router.post(
    "/{event_id}/poster",
    response_model=AttachmentOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_attachment_body_cap), Depends(rate_limit_attachments)],
    responses={**_ERRORS},
)
async def upload_poster(
    db: DbSession,
    settings: SettingsDep,
    storage: AttachmentStorage,
    queue: ScanQueueDep,
    principal: Annotated[Principal, Depends(require_any_scope("dossier.attach"))],
    event_id: UUID,
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str, Form(alias="altText")],
    credit: Annotated[str, Form()],
    rights_basis: Annotated[str, Form(alias="rightsBasis")],
    persons_depicted: Annotated[bool, Form(alias="personsDepicted")] = False,
    consent_note: Annotated[str | None, Form(alias="consentNote")] = None,
) -> AttachmentOut:
    """Upload the poster of a dossier; it starts in `pending` until ClamAV has scanned it."""
    meta = _meta(alt_text, credit, rights_basis, persons_depicted, consent_note)
    data = await _read_capped(file, settings.attachment_max_bytes)
    row = await posters.upload_poster(
        db,
        storage,
        principal,
        event_id,
        filename=file.filename,
        data=data,
        meta=meta,
        max_bytes=settings.attachment_max_bytes,
    )
    out = attachment_out(row)
    try:
        await db.commit()
    except BaseException:
        if storage is not None and row.storage_key is not None:
            with contextlib.suppress(StorageError):
                await storage.remove(row.storage_key)
        raise
    if queue is not None:
        await queue.enqueue(row.id)
    return out


@router.get(
    "/{event_id}/poster/file",
    responses={**_ERRORS},
    response_class=Response,
)
async def poster_file(
    db: DbSession,
    storage: PublicStorage,
    principal: Annotated[Principal, Depends(require_principal("library.read"))],
    event_id: UUID,
    variant: Annotated[PosterVariant, Query()] = "card1200",
) -> Response:
    """Return a derivative of the poster to a reader of the dossier (private cache)."""
    event = await load_visible(db, principal, event_id)
    poster = await poster_of(db, event)
    if poster is not None and poster.scan_status == "infected":
        raise ConflictError("The poster was quarantined.", code="quarantined")
    derivative = (poster.derivatives or {}).get(VARIANT_KEYS[variant]) if poster else None
    if derivative is None:
        raise NotFoundError("poster derivative not ready")
    if storage is None:
        raise ServiceUnavailableError("Object storage unavailable.")
    try:
        body = await storage.get(f"derivatives/{derivative['id']}.webp")
    except StorageError as exc:
        raise ServiceUnavailableError("Poster temporarily unavailable.") from exc
    return Response(
        body, media_type="image/webp", headers={"Cache-Control": "private, max-age=300"}
    )
