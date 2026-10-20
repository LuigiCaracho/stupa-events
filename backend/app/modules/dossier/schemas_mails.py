"""Wire shapes of the mail template facade."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import Field

from app.modules.auth.schemas import CamelModel
from app.modules.dossier.models_documents import MAX_BODY_CHARS
from app.modules.dossier.schemas import Visibility


class MailTemplateItem(CamelModel):
    """A mail template in the list."""

    id: UUID
    title: str
    subject: str
    visibility: Visibility
    rev: int
    updated_at: datetime


class MailTemplateOut(MailTemplateItem):
    """A mail template with its text."""

    event_id: UUID
    body_md: str
    to_hint: str | None
    placeholders: list[str]


class MailTemplatePut(CamelModel):
    """Body of `PUT /events/{id}/mail-templates/{docId}` (`new` creates)."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str = Field(max_length=1000)
    to_hint: str | None = Field(default=None, max_length=200)
    body_md: str = Field(max_length=MAX_BODY_CHARS)
    change_note: str | None = Field(default=None, max_length=500)
    visibility: Visibility | None = None


class RenderPreviewIn(CamelModel):
    """Body of `render-preview`: an unsaved draft, or nothing for the stored text."""

    subject: str | None = Field(default=None, max_length=1000)
    body_md: str | None = Field(default=None, max_length=MAX_BODY_CHARS)


class RenderPreviewOut(CamelModel):
    """The rendered plain-text mail."""

    subject: str
    body: str


class PlaceholderOut(CamelModel):
    """One entry of the placeholder catalog."""

    path: str
    label: str
    example: str
