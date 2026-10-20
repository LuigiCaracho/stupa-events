"""Worker job `derive_poster`: public WebP variants of a clean poster.

The job reads the stored poster from the private bucket, builds `thumb_400`, `card_1200`
and `og_1200x630` without metadata, writes them to the public bucket under
`derivatives/<sha256[:16]>-<variant>.webp` and stores their ids and sizes in
`attachment.derivatives`. A second run writes the same objects and the same row.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

from app.db import get_sessionmaker
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.files.models import Attachment
from app.modules.files.storage import ObjectStorage, StorageError, build_object_storage
from app.modules.media.derivatives import DERIVATIVE_SPECS, derivative_id, derive_webp
from app.modules.media.images import ImageRejected
from app.settings import Settings, load_settings

logger = logging.getLogger("app.dossier")


def derivative_key(derivative: str) -> str:
    """Return the object key of a derivative id in the public bucket."""
    return f"derivatives/{derivative}.webp"


def _public_storage(ctx: dict[str, Any]) -> ObjectStorage | None:
    if "public_storage" not in ctx:
        settings: Settings = ctx.get("settings") or load_settings()
        ctx["public_storage"] = build_object_storage(settings, bucket=settings.minio_public_bucket)
    return ctx["public_storage"]


async def derive_poster(ctx: dict[str, Any], attachment_id: str) -> str:
    """Build and store the public derivatives of a clean poster.

    Returns:
        `"derived"`, `"skipped"` (storage off, poster not clean or not a poster),
        `"gone"` (row or object missing) or `"rejected"` (the image cannot be decoded).
    """
    private = ctx.get("object_storage")
    public = _public_storage(ctx)
    if private is None or public is None:
        logger.warning("derive skipped (attachment=%s) - storage not configured", attachment_id)
        return "skipped"
    maker = ctx.get("files_sessionmaker") or get_sessionmaker()
    async with maker() as session:
        row = await session.get(Attachment, UUID(attachment_id))
        if row is None or row.storage_key is None:
            return "gone"
        if row.kind != "poster" or row.scan_status != "clean":
            return "skipped"
        try:
            source = await private.get(row.storage_key)
            derivatives: dict[str, dict[str, Any]] = {}
            for variant, spec in DERIVATIVE_SPECS.items():
                image = await asyncio.to_thread(derive_webp, source, spec)
                public_id = derivative_id(row.sha256, variant)
                await public.put(derivative_key(public_id), image.data, image.mime)
                derivatives[variant] = {
                    "id": public_id,
                    "width": image.width,
                    "height": image.height,
                }
        except ImageRejected:
            logger.warning("derive rejected (attachment=%s)", attachment_id)
            return "rejected"
        except StorageError:
            logger.warning("derive storage error (attachment=%s)", attachment_id)
            raise
        row.derivatives = derivatives
        await audit_record(
            session,
            actor=None,
            action=AuditAction.ATTACHMENT_SCAN,
            target_type="attachment",
            target_id=str(row.id),
            data={"eventId": str(row.event_id), "status": "derived"},
        )
        await session.commit()
    await _enqueue_followups(ctx, attachment_id)
    return "derived"


async def _enqueue_followups(ctx: dict[str, Any], attachment_id: str) -> None:
    """Hand the derived poster to the preview and promote jobs (idempotent job ids)."""
    pool = ctx.get("redis")
    if pool is None:
        return
    for task in ("build_preview", "promote_poster"):
        await pool.enqueue_job(task, attachment_id, _job_id=f"{task}:{attachment_id}")
