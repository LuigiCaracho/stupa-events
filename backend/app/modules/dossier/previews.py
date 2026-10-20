"""Worker job `build_preview`: the private WebP preview of a clean image attachment.

The preview lives in the private attachment bucket under `previews/<id>.webp`; the public
poster derivatives stay with `derive_poster`. A second run writes the same object.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.db import get_sessionmaker
from app.modules.files.models import Attachment
from app.modules.files.storage import StorageError
from app.modules.media.images import ImageRejected
from app.modules.media.preview import preview_webp

logger = logging.getLogger("app.dossier")


async def build_preview(ctx: dict[str, Any], attachment_id: str) -> str:
    """Build and store the preview of a clean image.

    Returns:
        `"built"`, `"skipped"` (storage off, not clean, not an image), `"gone"` or `"rejected"`.
    """
    storage = ctx.get("object_storage")
    if storage is None:
        return "skipped"
    maker = ctx.get("files_sessionmaker") or get_sessionmaker()
    async with maker() as session:
        row = await session.get(Attachment, UUID(attachment_id))
        if row is None or row.storage_key is None:
            return "gone"
        if row.scan_status != "clean" or not row.mime.startswith("image/"):
            return "skipped"
        try:
            image = await asyncio.to_thread(preview_webp, await storage.get(row.storage_key))
            key = f"previews/{row.id}.webp"
            await storage.put(key, image.data, image.mime)
        except ImageRejected:
            logger.warning("preview rejected (attachment=%s)", attachment_id)
            return "rejected"
        except StorageError:
            logger.warning("preview storage error (attachment=%s)", attachment_id)
            raise
        row.preview_key = key
        await session.commit()
    return "built"
