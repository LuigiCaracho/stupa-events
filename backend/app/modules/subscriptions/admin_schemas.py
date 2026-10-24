"""Wire shapes of the admin data request and erasure (B3-KONTRAKT 5.6).

The export confirms a hit without repeating the address (the asker knows it) and never shows
a token or a token hash.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated

from pydantic import StringConstraints

from app.modules.auth.schemas import CamelModel


class SubscriberAddressIn(CamelModel):
    """The address to look up or erase."""

    email: Annotated[str, StringConstraints(min_length=3, max_length=320)]


class ExportProfile(CamelModel):
    """The profile of the subscriber."""

    interests: list[str]
    categories: list[str]
    mail_enabled: bool
    created_at: datetime
    last_fetched_on: date | None


class ExportOutbox(CamelModel):
    """One queued Listmonk change."""

    op: str
    state: str
    created_at: datetime


class ExportListmonk(CamelModel):
    """What Listmonk holds: presence and the list keys."""

    present: bool
    lists: list[str]


class SubscriberExportOut(CamelModel):
    """Answer to a data request (GDPR information)."""

    found: bool
    status: str | None = None
    created_at: datetime | None = None
    consent_text_version: str | None = None
    consent_categories: list[str] = []
    consent_at: datetime | None = None
    confirmed_at: datetime | None = None
    unsubscribed_at: datetime | None = None
    profile: ExportProfile | None = None
    outbox: list[ExportOutbox] = []
    listmonk: ExportListmonk | None = None
