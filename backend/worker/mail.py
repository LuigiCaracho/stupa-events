"""arq worker task: mail dispatch.

`send_mail` rebuilds the `MailMessage` from the queue payload and sends it with the
`MailSender` in `ctx`. Production uses SMTP. Dev and test capture the mail. On an
error the task raises `arq.Retry` with a linear backoff up to `mail_max_tries`. After
that the job is dead: the worker logs it and never requeues it again. The `_job_id`
at enqueue equals the idempotency key. It stops a duplicate job for a send that
already runs or already finished.

Copied from STUPA-Workflow@93c33d6 backend/worker/mail.py (adds `send_due_reminders`)
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from arq import Retry
from sqlalchemy import Date, DateTime, Text, Uuid, cast, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import column, table

from app.db import get_sessionmaker
from app.modules.events.models import Event
from app.modules.notifications.mail import (
    CapturingMailSender,
    MailMessage,
    MailSender,
    SmtpMailSender,
)
from app.modules.notifications.service import dispatch_mails, notify
from app.settings import Settings, load_settings
from app.shared.timeutil import DEFAULT_TZID, utcnow

logger = logging.getLogger("app.mail")

_ITEM = table(
    "checklist_item",
    column("id", Uuid),
    column("event_id", Uuid),
    column("text", Text),
    column("assignee_sub", Text),
    column("due_at", DateTime(timezone=True)),
    column("done_at", DateTime(timezone=True)),
    column("waived_reason", Text),
    column("notified_due_for", Date),
)
DUE_BATCH = 500


def build_sender(settings: Settings) -> MailSender:
    """Return the SMTP sender when SMTP is configured, else a capturing sender.

    The capturing sender serves dev and test. It sends no real mail.
    """
    if settings.smtp_enabled:
        return SmtpMailSender(settings)
    logger.warning("SMTP not configured — mails are captured/dropped (no real send)")
    return CapturingMailSender()


async def on_startup(ctx: dict[str, Any]) -> None:
    settings = load_settings()
    ctx["settings"] = settings
    ctx["mail_sender"] = build_sender(settings)


async def send_mail(ctx: dict[str, Any], payload: dict[str, object]) -> str:
    """Send one mail.

    On an error the task retries with a linear backoff up to `mail_max_tries`. After
    the last try the job is dead and the worker logs it.

    Returns:
        `"sent"` after delivery, or `"dead"` after the last failed try.
    """
    settings: Settings = ctx["settings"]
    sender: MailSender = ctx["mail_sender"]
    msg = MailMessage.from_payload(payload)
    try:
        await sender.send(msg)
    except Exception as exc:  # noqa: BLE001 - transient SMTP error -> retry
        job_try = int(ctx.get("job_try", 1))
        if job_try >= settings.mail_max_tries:
            logger.error(
                "mail send failed permanently after %s tries (domains=%s key=%s)",
                job_try,
                msg.recipient_domains(),
                msg.idempotency_key,
            )
            return "dead"
        defer = settings.mail_retry_backoff_seconds * job_try
        logger.warning(
            "mail send failed (try=%s, retry in %ss, key=%s): %s",
            job_try,
            defer,
            msg.idempotency_key,
            type(exc).__name__,
        )
        raise Retry(defer=defer) from exc
    return "sent"


def _sessionmaker(ctx: dict[str, Any]) -> async_sessionmaker[AsyncSession]:
    maker = ctx.get("mail_sessionmaker")
    return maker if maker is not None else get_sessionmaker()


def tomorrow_local(now: datetime) -> date:
    """Return tomorrow's date in Europe/Berlin (arq cron runs in UTC)."""
    return now.astimezone(ZoneInfo(DEFAULT_TZID)).date() + timedelta(days=1)


async def send_due_reminders(ctx: dict[str, Any]) -> str:
    """Notify the assignees of open checklist items that are due tomorrow.

    The item's local due date (in the dossier's time zone) must equal tomorrow in
    Europe/Berlin and differ from `notified_due_for`; the job stores the date, so a second
    run sends nothing and a new due date triggers a new reminder.

    Returns:
        The log line.
    """
    if ctx.get("redis") is None:
        return "send_due_reminders: skipped (no queue)"
    tomorrow = tomorrow_local(utcnow())
    due_local = cast(func.timezone(Event.tzid, _ITEM.c.due_at), Date)
    pending = []
    async with _sessionmaker(ctx)() as session:
        rows = (
            await session.execute(
                select(_ITEM.c.id, _ITEM.c.text, _ITEM.c.assignee_sub, Event)
                .join(Event, Event.id == _ITEM.c.event_id)
                .where(
                    _ITEM.c.assignee_sub.is_not(None),
                    _ITEM.c.done_at.is_(None),
                    _ITEM.c.waived_reason.is_(None),
                    due_local == tomorrow,
                    _ITEM.c.notified_due_for.is_distinct_from(tomorrow),
                )
                .limit(DUE_BATCH)
            )
        ).all()
        for item_id, text, sub, event in rows:
            await session.execute(
                update(_ITEM).where(_ITEM.c.id == item_id).values(notified_due_for=tomorrow)
            )
            pending += await notify(
                session,
                "checklist_due",
                [sub],
                event,
                {"itemText": text, "dueDate": tomorrow.strftime("%d.%m.%Y")},
                f"checklist_due:{item_id}:{tomorrow.isoformat()}",
            )
        await session.commit()
    await dispatch_mails(ctx.get("redis"), pending)
    return f"send_due_reminders: items={len(rows)} mails={len(pending)}"
