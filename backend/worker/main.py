"""arq worker: entry points, function registry and the nightly audit check.

`ping` does nothing and serves the container healthcheck. Modules add their jobs through
a `WORKER_FUNCTIONS` tuple; the dossier module lists `derive_poster` there. The queue
name comes from `ARQ_QUEUE_NAME`.

Copied from STUPA-Workflow@93c33d6 backend/worker/main.py (mail, scan, audit only)
"""

from __future__ import annotations

import os
from typing import Any

from arq import cron, func
from arq.connections import RedisSettings

from app.modules.dossier.worker_jobs import WORKER_FUNCTIONS
from worker.advance import archive_ended, purge_drafts
from worker.audit_verify import process_audit_verification
from worker.gc import gc_media, gc_notifications
from worker.mail import on_startup as mail_on_startup
from worker.mail import send_due_reminders, send_mail
from worker.public_cache import rebuild_public_cache
from worker.scan import on_startup as scan_on_startup
from worker.scan import requeue_stale_scans, scan_attachment

AUDIT_VERIFY_JOB_TIMEOUT_SECONDS = 7200.0


async def ping(ctx: dict[str, object]) -> str:
    """Do nothing and serve the container healthcheck."""
    return "pong"


async def _on_startup(ctx: dict[str, Any]) -> None:
    """Set up the mail and scan dependencies."""
    await mail_on_startup(ctx)
    await scan_on_startup(ctx)


class WorkerSettings:
    """arq settings of the worker process."""

    functions = [
        ping,
        send_mail,
        send_due_reminders,
        func(rebuild_public_cache, keep_result=0, timeout=300),
        gc_media,
        gc_notifications,
        scan_attachment,
        requeue_stale_scans,
        func(process_audit_verification, timeout=AUDIT_VERIFY_JOB_TIMEOUT_SECONDS),
        archive_ended,
        purge_drafts,
        *WORKER_FUNCTIONS,
    ]
    cron_jobs = [
        cron(
            process_audit_verification,
            hour=4,
            minute=30,
            timeout=AUDIT_VERIFY_JOB_TIMEOUT_SECONDS,
        ),
        cron(archive_ended, minute={0, 15, 30, 45}, timeout=300, unique=True),
        cron(purge_drafts, hour=3, minute=30),
        cron(gc_notifications, hour=3, minute=40),
        cron(gc_media, hour=3, minute=50),
        cron(send_due_reminders, minute=10, timeout=300, unique=True),
        cron(rebuild_public_cache, minute=5, timeout=300, unique=True, keep_result=0),
        cron(requeue_stale_scans, minute={3, 13, 23, 33, 43, 53}, timeout=120, unique=True),
    ]
    on_startup = _on_startup
    queue_name = os.environ.get("ARQ_QUEUE_NAME", "events")
    redis_settings = RedisSettings.from_dsn(os.environ.get("REDIS_URL", "redis://redis:6379/0"))
