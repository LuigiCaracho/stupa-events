"""The three system mails of the subscription flows, as ready-to-queue messages.

`doi` asks to confirm, `already` tells a known address that nothing changed and offers the
management link, `manage_link` is the requested magic link. The mail text carries the link
with its token; the token exists nowhere else in clear text. Only domains reach the log.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.modules.notifications.mail import MailMessage, compute_idempotency_key
from app.modules.notifications.render import absolute_link, render_system_mail
from app.settings import Settings


def _message(kind: str, to: str, ctx: dict[str, object], key: str) -> MailMessage:
    subject, text, html = render_system_mail(kind, ctx)
    return MailMessage(to=(to,), subject=subject, text=text, html=html, idempotency_key=key)


def doi_mail(
    settings: Settings,
    *,
    to: str,
    subscriber_id: UUID,
    token: str,
    token_hash: str,
    categories: Sequence[str],
) -> MailMessage:
    """Build the confirmation mail; `categories` are the labels the person chose."""
    link = absolute_link(settings.public_base_url, f"/bestaetigen/{token}")
    key = compute_idempotency_key("doi", str(subscriber_id), token_hash)
    return _message("doi", to, {"link": link, "categories": list(categories)}, key)


def already_mail(
    settings: Settings, *, to: str, subscriber_id: UUID, token: str, token_hash: str
) -> MailMessage:
    """Build the note for an address that is already subscribed."""
    link = absolute_link(settings.public_base_url, f"/abo/{token}")
    key = compute_idempotency_key("already", str(subscriber_id), token_hash)
    return _message("already", to, {"link": link}, key)


def manage_link_mail(
    settings: Settings, *, to: str, subscriber_id: UUID, token: str, token_hash: str
) -> MailMessage:
    """Build the magic-link mail."""
    link = absolute_link(settings.public_base_url, f"/abo/{token}")
    key = compute_idempotency_key("manage", str(subscriber_id), token_hash)
    return _message("manage_link", to, {"link": link}, key)
