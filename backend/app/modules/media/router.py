"""Media routes: upload and stream the images of the Markdown texts (M4 contract 8).

`POST /api/media/images` takes one image from a principal who may write comments or edit a
dossier. `GET /api/media/images/{id}` streams one image to any session; the random uuid4 is
the permission, as in the upstream (no uploader column, no personal data in the image).
Every answer is inline, `nosniff` and carries `default-src 'none'; sandbox`.

Pattern from STUPA-Workflow@93c33d6 backend/app/modules/media/router.py (sessions only)
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Request, UploadFile, status
from fastapi.responses import StreamingResponse

from app.deps import DbSession, SettingsDep, require_any_scope, require_principal
from app.modules.auth.principal import Principal
from app.modules.dossier.deps import AttachmentStorage
from app.modules.media.schemas import MarkdownImageOut
from app.modules.media.service import ImageStream, MediaService
from app.shared.antiabuse import rate_limit_media_images
from app.shared.errors import PayloadTooLargeError, ProblemDetail

router = APIRouter(tags=["media"])

IMAGE_CSP = "default-src 'none'; sandbox"
_PRIVATE_CACHE = "private, max-age=3600"
_FRAME_BYTES = 64 * 1024
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}


def _errors(*codes: int) -> dict[int | str, dict[str, Any]]:
    return {code: _PROBLEM for code in codes}


def get_media_service(
    session: DbSession, storage: AttachmentStorage, settings: SettingsDep
) -> MediaService:
    """Wire the service with the optional private object storage."""
    return MediaService(session, storage=storage, max_bytes=settings.markdown_image_max_bytes)


ServiceDep = Annotated[MediaService, Depends(get_media_service)]
Uploader = Annotated[Principal, Depends(require_any_scope("comment.write", "event.edit"))]
Reader = Annotated[Principal, Depends(require_principal("library.read"))]


def enforce_media_body_cap(request: Request, settings: SettingsDep) -> None:
    """Answer 413 when the `Content-Length` clearly exceeds the image limit."""
    limit = settings.markdown_image_max_bytes + _FRAME_BYTES
    raw = request.headers.get("content-length")
    if raw is not None and raw.isdigit() and int(raw) > limit:
        raise PayloadTooLargeError(f"Request body exceeds {limit} bytes.")


def _image_response(image: ImageStream) -> StreamingResponse:
    return StreamingResponse(
        image.stream,
        media_type=image.mime,
        headers={
            "Content-Disposition": "inline",
            "Content-Length": str(image.size),
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": IMAGE_CSP,
            "Cache-Control": _PRIVATE_CACHE,
        },
    )


@router.post(
    "/media/images",
    response_model=MarkdownImageOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(enforce_media_body_cap), Depends(rate_limit_media_images)],
    responses=_errors(401, 403, 413, 415, 429, 503),
)
async def upload_image(
    service: ServiceDep, _: Uploader, file: Annotated[UploadFile, File()]
) -> MarkdownImageOut:
    """Upload one image for a Markdown text; the answer names the canonical path."""
    data = await file.read(service.max_bytes + 1)
    return await service.upload(data)


@router.get(
    "/media/images/{image_id}",
    response_class=StreamingResponse,
    responses=_errors(401, 404, 503),
)
async def get_image(image_id: UUID, service: ServiceDep, _: Reader) -> StreamingResponse:
    """Stream one image to a signed-in session."""
    return _image_response(await service.open(image_id))
