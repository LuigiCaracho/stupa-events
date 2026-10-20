"""arq worker task: ClamAV scan of an attachment.

`scan_attachment` loads the object from MinIO and scans it with ClamAV. It writes the
result to `attachment.scan_status` and an audit entry in the same transaction. On a hit
it deletes the object, clears `storage_key` and keeps the signature in `scan_result`.
After a clean scan of a poster it enqueues `derive_poster`, which builds the public WebP
derivatives. After a clean scan of a replacement (not a poster) the predecessor is hidden,
so an infected or failed replacement never hides the last good version. `requeue_stale_scans`
(cron) queues `pending` rows again whose job never ran, for example after a Redis outage.
A transient storage or scanner error raises `arq.Retry` with a linear
backoff up to `scan_max_tries`. After the last try the job is dead: the worker logs it, sets
`scan_status='error'` with an audit entry and never requeues it again.
Idempotency comes from the job key `scan:<id>`. A second run on an already scanned
attachment writes the same result.

A row can disappear during the scan. The task then returns `"gone"` and writes nothing.

Copied from STUPA-Workflow@93c33d6 backend/worker/scan.py (event attachments, derive hand-off)
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any
from uuid import UUID

from arq import Retry
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db import get_sessionmaker
from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.files.models import Attachment
from app.modules.files.scanner import ScannerError, ScanVerdict, build_scanner
from app.modules.files.storage import ObjectStorage, StorageError, build_object_storage
from app.settings import Settings, load_settings
from app.shared.timeutil import utcnow

logger = logging.getLogger("app.files")

DERIVE_TASK_NAME = "derive_poster"
PREVIEW_TASK_NAME = "build_preview"
STALE_AFTER = timedelta(minutes=10)
REQUEUE_BATCH = 100


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = load_settings()
    ctx["settings"] = settings
    ctx["scanner"] = build_scanner(settings)
    ctx["object_storage"] = build_object_storage(settings)


def _sessionmaker(ctx: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    """Return the DB sessionmaker (tests inject one via `ctx['files_sessionmaker']`)."""
    maker = ctx.get("files_sessionmaker")
    return maker if maker is not None else get_sessionmaker()


async def scan_attachment(ctx: dict[str, Any], attachment_id: str) -> str:
    """Scan an attachment and store the result.

    A transient error retries with a linear backoff.

    Returns:
        `"skipped"` without ClamAV or storage, `"gone"` when the attachment is gone
        before the scan,
        `"clean"` or `"infected"` after a scan, and `"dead"` after the last failed try.
    """
    settings: Settings = ctx["settings"]
    scanner = ctx.get("scanner")
    storage = ctx.get("object_storage")
    if scanner is None or storage is None:
        logger.warning(
            "scan skipped (attachment=%s) — clamav/storage not configured", attachment_id
        )
        return "skipped"

    aid = UUID(attachment_id)
    maker = _sessionmaker(ctx)
    async with maker() as session:
        attachment = await session.get(Attachment, aid)
        if attachment is None or attachment.storage_key is None:
            logger.info("scan target %s gone — skipped", attachment_id)
            return "gone"
        try:
            data = await storage.get(attachment.storage_key)
            verdict = await scanner.scan(data)
        except (StorageError, ScannerError) as exc:
            outcome = _retry_or_dead(ctx, settings, attachment_id, exc)
            await _store_error(session, attachment)
            await session.commit()
            return outcome
        await _store_verdict(session, storage, attachment, verdict)
        if verdict.clean:
            await _retire_predecessor(session, attachment)
        await session.commit()
    if verdict.clean and attachment.kind == "poster":
        await _enqueue_derive(ctx, aid)
    elif verdict.clean and attachment.mime.startswith("image/"):
        await _enqueue_job(ctx, PREVIEW_TASK_NAME, aid)
    return "clean" if verdict.clean else "infected"


async def _retire_predecessor(session: AsyncSession, attachment: Attachment) -> None:
    if attachment.kind == "poster" or attachment.supersedes_id is None:
        return
    await session.execute(
        update(Attachment)
        .where(Attachment.id == attachment.supersedes_id, Attachment.retired_at.is_(None))
        .values(retired_at=utcnow())
    )


async def requeue_stale_scans(ctx: dict[str, Any]) -> int:
    """Queue the scan again for `pending` attachments older than ten minutes."""
    pool = ctx.get("redis")
    if pool is None:
        return 0
    async with _sessionmaker(ctx)() as session:
        ids = list(
            await session.scalars(
                select(Attachment.id)
                .where(
                    Attachment.scan_status == "pending",
                    Attachment.storage_key.is_not(None),
                    Attachment.created_at < utcnow() - STALE_AFTER,
                )
                .limit(REQUEUE_BATCH)
            )
        )
    for attachment_id in ids:
        await pool.enqueue_job(
            "scan_attachment", str(attachment_id), _job_id=f"scan:{attachment_id}"
        )
    return len(ids)


async def _store_verdict(
    session: AsyncSession,
    storage: ObjectStorage,
    attachment: Attachment,
    verdict: ScanVerdict,
) -> None:
    """Write the verdict, quarantine a finding and record the audit entry."""
    data = {"attachmentId": str(attachment.id), "eventId": str(attachment.event_id)}
    if verdict.clean:
        attachment.scan_status = "clean"
        attachment.scan_result = "clean"
        await audit_record(
            session,
            actor=None,
            action=AuditAction.ATTACHMENT_SCAN,
            target_type="attachment",
            target_id=str(attachment.id),
            data={**data, "status": "clean"},
        )
        return
    if attachment.storage_key is not None:
        await storage.remove(attachment.storage_key)
    attachment.storage_key = None
    attachment.scan_status = "infected"
    attachment.scan_result = verdict.signature or "unknown"
    await audit_record(
        session,
        actor=None,
        action=AuditAction.ATTACHMENT_QUARANTINE,
        target_type="attachment",
        target_id=str(attachment.id),
        data={**data, "signature": attachment.scan_result},
    )


async def _store_error(session: AsyncSession, attachment: Attachment) -> None:
    """Mark a scan that ran out of tries as `error` and leave an audit entry."""
    attachment.scan_status = "error"
    await audit_record(
        session,
        actor=None,
        action=AuditAction.ATTACHMENT_SCAN,
        target_type="attachment",
        target_id=str(attachment.id),
        data={
            "attachmentId": str(attachment.id),
            "eventId": str(attachment.event_id),
            "status": "error",
        },
    )


async def _enqueue_job(ctx: dict[str, Any], task: str, attachment_id: UUID) -> None:
    """Hand a clean attachment to a follow-up job (idempotent through the job id)."""
    pool = ctx.get("redis")
    if pool is None:
        logger.warning("%s skipped (attachment=%s) - no redis pool", task, attachment_id)
        return
    await pool.enqueue_job(task, str(attachment_id), _job_id=f"{task}:{attachment_id}")


async def _enqueue_derive(ctx: dict[str, Any], attachment_id: UUID) -> None:
    """Hand a clean poster to the derive job (idempotent through the job id)."""
    await _enqueue_job(ctx, DERIVE_TASK_NAME, attachment_id)


def _retry_or_dead(
    ctx: dict[str, Any], settings: Settings, attachment_id: str, exc: Exception
) -> str:
    """Schedule a backoff retry, or give up after the last try.

    Returns:
        `"dead"` after `scan_max_tries` failed tries. The worker never requeues the job
        again.

    Raises:
        Retry: The task still has tries left.
    """
    job_try = int(ctx.get("job_try", 1))
    if job_try >= settings.scan_max_tries:
        logger.error(
            "scan failed permanently after %s tries (attachment=%s): %s",
            job_try,
            attachment_id,
            type(exc).__name__,
        )
        return "dead"
    defer = settings.scan_retry_backoff_seconds * job_try
    logger.warning(
        "scan failed (try=%s, retry in %ss, attachment=%s): %s",
        job_try,
        defer,
        attachment_id,
        type(exc).__name__,
    )
    raise Retry(defer=defer) from exc
