"""Create notifications: inbox rows in the transaction of the cause, mails after the commit.

`notify` is the hook that pipeline, comments and checklist call after the factual change.
It inserts the inbox rows (respecting `notification_pref.in_app`, essential kinds always)
and returns the mails to send. After the commit the caller passes them to `dispatch_mails`,
which claims `notif:<id>:mail` in Redis (SET NX) and enqueues them. Without a pool the mail
is dropped with a warning that carries no address; the inbox row and the cause stay intact.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Principal
from app.modules.events.models import Event
from app.modules.notifications.kinds import Kind, kind_of
from app.modules.notifications.mail import MailMessage, compute_idempotency_key
from app.modules.notifications.models import Notification, NotificationPref
from app.modules.notifications.provider import mail_queue_from_pool
from app.modules.notifications.queue import NullMailQueue
from app.modules.notifications.recipients import clean, recipients_for
from app.modules.notifications.render import absolute_link, render_system_mail
from app.modules.notifications.templating import TemplateRenderError
from app.settings import Settings, get_settings

logger = logging.getLogger("app.mail")

MAIL_KEY_TTL_SECONDS = 24 * 3600
MAIL_ONLY_PARAMS = frozenset({"itemText"})
_TAB = {
    "comment_added": "/verlauf",
    "comment_resolved": "/verlauf",
    "task_assigned": "/checkliste",
    "checklist_due": "/checkliste",
    "followup_reminder": "/nachbereitung",
    "auto_archived": "/nachbereitung",
}
MISSING_LABELS = {
    "retrospective": "Rückblick",
    "outcome": "Ergebnis",
    "howto": "Anleitung prüfen",
    "checklist": "offene Pflichtpunkte der Checkliste",
}


@dataclass(frozen=True, slots=True)
class PendingMail:
    """A mail that waits for the commit of its cause."""

    notification_id: UUID
    message: MailMessage


def event_link(kind: str, event_id: UUID) -> str:
    """Return the site-relative link of the dossier tab that a kind points to."""
    return f"/dossiers/{event_id}{_TAB.get(kind, '')}"


async def _prefs(session: AsyncSession, kind: str, subs: list[str]) -> dict[str, NotificationPref]:
    rows = await session.execute(
        select(NotificationPref).where(
            NotificationPref.kind == kind, NotificationPref.principal_sub.in_(subs)
        )
    )
    return {p.principal_sub: p for p in rows.scalars()}


async def _emails(session: AsyncSession, subs: list[str]) -> dict[str, str]:
    rows = await session.execute(
        select(Principal.sub, Principal.email).where(
            Principal.sub.in_(subs), Principal.email.is_not(None), Principal.active.is_(True)
        )
    )
    return {sub: str(email) for sub, email in rows.all()}


def _switch(kind: Kind, pref: NotificationPref | None) -> tuple[bool, bool]:
    if pref is None or kind.essential:
        return True, kind.mail
    return pref.in_app, kind.mail and pref.mail


def _build_mail(
    kind: str,
    nid: UUID,
    to: str,
    params: Mapping[str, Any],
    link: str,
    settings: Settings,
) -> PendingMail | None:
    ctx = {
        "title": params.get("eventTitle", ""),
        "actor": params.get("actorName", "Jemand"),
        "item": params.get("itemText", ""),
        "due": params.get("dueDate", ""),
        "days": params.get("daysOpen", 0),
        "missing": ", ".join(MISSING_LABELS[m] for m in params.get("missing", ())),
        "howto_unverified": bool(params.get("howtoUnverified", False)),
        "link": absolute_link(settings.public_base_url, link),
        "prefs_link": absolute_link(settings.public_base_url, "/konto"),
    }
    try:
        subject, text, html = render_system_mail(kind, ctx)
    except TemplateRenderError:
        logger.exception("mail render failed (kind=%s)", kind)
        return None
    msg = MailMessage(
        to=(to,),
        subject=subject,
        text=text,
        html=html,
        idempotency_key=compute_idempotency_key("notif", str(nid)),
    )
    return PendingMail(nid, msg)


async def _insert(
    session: AsyncSession, row: dict[str, Any], dedupe_key: str | None
) -> UUID | None:
    stmt = pg_insert(Notification).values(**row, dedupe_key=dedupe_key)
    stmt = stmt.on_conflict_do_nothing(index_elements=["dedupe_key"]).returning(Notification.id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def notify(
    session: AsyncSession,
    kind: str,
    recipients: Iterable[str],
    event: Event,
    params: Mapping[str, Any],
    dedupe_key: str | None = None,
    *,
    actor_sub: str | None = None,
    settings: Settings | None = None,
) -> list[PendingMail]:
    """Insert the inbox rows of a kind and return the mails to send after the commit.

    Args:
        session: The session of the cause; the rows share its transaction.
        kind: A key of the kind catalog.
        recipients: Subs to notify; the actor and `system:` subs are dropped.
        event: The dossier (id and title are used).
        params: Display values (`actorName`, `dueDate`) stored with the row; `itemText` is
            free text and goes into the mail only, never into `notification.params`.
        dedupe_key: Stops double rows; stored as `<key>:<sub>` per recipient.
        actor_sub: The acting person, who never gets a notification of their own action.
        settings: Settings override for tests.

    Returns:
        The mails that `dispatch_mails` sends after the commit.

    Raises:
        KeyError: The kind is not in the catalog.
    """
    spec = kind_of(kind)
    settings = settings or get_settings()
    subs = clean(recipients, actor_sub)
    if not subs:
        return []
    prefs = await _prefs(session, kind, subs)
    emails = await _emails(session, subs)
    link = event_link(kind, event.id)
    mail_params = {"eventTitle": event.title, **params}
    stored = {k: v for k, v in mail_params.items() if k not in MAIL_ONLY_PARAMS}
    pending: list[PendingMail] = []
    for sub in subs:
        in_app, mail = _switch(spec, prefs.get(sub))
        nid: UUID | None = uuid4()
        if in_app:
            row = {
                "recipient_sub": sub,
                "kind": kind,
                "event_id": event.id,
                "params": stored,
                "link": link,
            }
            nid = await _insert(session, row, f"{dedupe_key}:{sub}" if dedupe_key else None)
        if nid is None or not mail or sub not in emails:
            continue
        built = _build_mail(kind, nid, emails[sub], mail_params, link, settings)
        if built is not None:
            pending.append(built)
    return pending


async def notify_event(
    session: AsyncSession,
    kind: str,
    event: Event,
    params: Mapping[str, Any],
    dedupe_key: str | None = None,
    *,
    actor_sub: str | None = None,
    extra_recipients: Iterable[str] = (),
) -> list[PendingMail]:
    """Resolve the recipients of a group kind (table 5.7) and call `notify`."""
    subs = [*await recipients_for(session, kind, event, actor_sub), *extra_recipients]
    return await notify(session, kind, subs, event, params, dedupe_key, actor_sub=actor_sub)


async def dispatch_mails(pool: Any | None, pending: Iterable[PendingMail]) -> None:
    """Enqueue the mails after the commit; a missing or failing Redis drops them."""
    mails = list(pending)
    if not mails:
        return
    queue = mail_queue_from_pool(pool) or NullMailQueue()
    for item in mails:
        key = f"notif:{item.notification_id}:mail"
        claimed = False
        try:
            if pool is not None:
                if not await pool.set(key, "1", nx=True, ex=MAIL_KEY_TTL_SECONDS):
                    continue
                claimed = True
            await queue.enqueue(item.message)
        except Exception:  # noqa: BLE001 - a mail never fails the cause
            logger.warning("mail dropped, queue error (key=%s)", item.message.idempotency_key)
            if claimed and pool is not None:
                with contextlib.suppress(Exception):
                    await pool.delete(key)
