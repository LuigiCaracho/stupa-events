"""Media service: store and serve the images of the Markdown texts.

``upload`` takes the bytes of one file. It cleans them (``images.clean_image``: sniff,
decode, strip the metadata, downscale, encode again), stores the result under
``media/images/<id>`` in the attachment bucket and inserts the ``markdown_image``
row. The stored bytes come from Pillow, never from the client, so an image gets no
ClamAV scan. At most ``CLEAN_CONCURRENCY`` cleans run at the same time in one process.

``open`` streams one image. The router applies the read rule before.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/media/service.py (no render assets)
"""

from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Final

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.storage import ObjectStorage, StorageError
from app.modules.media.images import CleanImage, ImageRejected, clean_image
from app.modules.media.models import MarkdownImage, image_storage_key
from app.modules.media.refs import image_path
from app.modules.media.schemas import MarkdownImageOut
from app.shared.errors import (
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    UnsupportedMediaTypeError,
)

logger = logging.getLogger("app.media")

#: The most image cleans that run at the same time in one process.
CLEAN_CONCURRENCY: Final[int] = 2

# The clean is CPU and memory work in a thread. The semaphore holds the number of
# parallel cleans in one process at ``CLEAN_CONCURRENCY``, so parallel uploads cannot
# take all the CPU or the memory of the API.
_clean_slots: Final[asyncio.Semaphore] = asyncio.Semaphore(CLEAN_CONCURRENCY)
# A cancelled request releases ``_clean_slots`` while its thread still works. The
# thread semaphore holds the limit in that case too.
_clean_threads: Final[threading.BoundedSemaphore] = threading.BoundedSemaphore(CLEAN_CONCURRENCY)


def _clean_bounded(data: bytes) -> CleanImage:
    """Run ``clean_image`` in one of the ``CLEAN_CONCURRENCY`` thread slots."""
    with _clean_threads:
        return clean_image(data)


@dataclass(frozen=True, slots=True)
class ImageStream:
    """The bytes of one stored image and their headers."""

    stream: AsyncIterator[bytes]
    mime: str
    size: int


class MediaService:
    """Upload and read the Markdown images."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        storage: ObjectStorage | None,
        max_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        self.session = session
        self.storage = storage
        self.max_bytes = max_bytes

    async def upload(self, data: bytes) -> MarkdownImageOut:
        """Clean and store one image.

        Raises:
            ServiceUnavailableError: The storage is off or failed (503).
            UnsupportedMediaTypeError: The file is no accepted image (415).
            PayloadTooLargeError: The encoded image is larger than ``max_bytes`` (413).
        """
        if self.storage is None:
            raise ServiceUnavailableError("Object storage unavailable.")
        try:
            async with _clean_slots:
                image = await asyncio.to_thread(_clean_bounded, data)
        except ImageRejected as exc:
            raise UnsupportedMediaTypeError(str(exc)) from exc
        if len(image.data) > self.max_bytes:
            raise PayloadTooLargeError(f"Image exceeds {self.max_bytes} bytes.")
        image_id = uuid.uuid4()
        row = MarkdownImage(
            id=image_id,
            storage_key=image_storage_key(image_id),
            mime=image.mime,
            size=len(image.data),
            width=image.width,
            height=image.height,
        )
        self.session.add(row)
        await self.session.flush()
        try:
            await self.storage.put(row.storage_key, image.data, image.mime)
        except StorageError as exc:
            raise ServiceUnavailableError("Object storage write failed.") from exc
        await self.session.commit()
        logger.info("markdown image stored", extra={"image_id": str(image_id)})
        return MarkdownImageOut(
            id=image_id,
            url=image_path(image_id),
            mime=row.mime,
            width=row.width,
            height=row.height,
            size=row.size,
        )

    async def open(self, image_id: uuid.UUID) -> ImageStream:
        """Return the stream of one image.

        Raises:
            NotFoundError: The id is unknown (404).
            ServiceUnavailableError: The storage is off or failed (503).
        """
        row = await self.session.get(MarkdownImage, image_id)
        if row is None:
            raise NotFoundError("image not found")
        if self.storage is None:
            raise ServiceUnavailableError("Object storage unavailable.")
        try:
            stream = await self.storage.get_stream(row.storage_key)
        except StorageError as exc:
            raise ServiceUnavailableError("Image temporarily unavailable.") from exc
        return ImageStream(stream=stream, mime=row.mime, size=row.size)
