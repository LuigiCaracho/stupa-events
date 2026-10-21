"""Wire shapes of documents, their revisions, the diff and the document draft."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.modules.auth.schemas import CamelModel
from app.modules.dossier.models_documents import MAX_BODY_CHARS
from app.modules.dossier.schemas import Visibility

RETROSPECTIVE_TITLE = "Rückblick"
Title = Field(min_length=1, max_length=200)
Body = Field(max_length=MAX_BODY_CHARS)


class DocumentItem(CamelModel):
    """A document in a list, without its text."""

    id: UUID
    kind: str
    title: str
    visibility: Visibility
    carry_over: bool
    rev: int
    verified_at: datetime | None
    verified_by: str | None
    updated_at: datetime


class DocumentOut(DocumentItem):
    """A document with its text."""

    event_id: UUID | None
    format_id: UUID | None = None
    body_md: str
    meta: dict


class DocumentCreate(CamelModel):
    """Body of `POST /events/{id}/documents`."""

    kind: Literal["howto", "notes", "retrospective"]
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body_md: str = Body
    visibility: Visibility | None = None
    carry_over: bool | None = None

    @model_validator(mode="after")
    def _title_default(self) -> Self:
        if self.title is None:
            if self.kind != "retrospective":
                raise ValueError("title is required")
            self.title = RETROSPECTIVE_TITLE
        return self


class DocumentPut(CamelModel):
    """Body of `PUT /documents/{id}`; `If-Match` names the revision."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    body_md: str = Body
    change_note: str | None = Field(default=None, max_length=500)
    visibility: Visibility | None = None
    carry_over: bool | None = None


class RevisionItem(CamelModel):
    """A revision in the history list."""

    rev: int
    actor_id: str | None
    actor_type: str
    change_note: str | None
    at: datetime
    title_changed: bool
    chars_delta: int


class RevisionOut(CamelModel):
    """A full revision."""

    rev: int
    title: str
    body_md: str
    meta: dict
    actor_id: str | None
    actor_type: str
    change_note: str | None
    at: datetime


class DiffLine(CamelModel):
    """One line of the diff; `from_line`/`to_line` are 1-based or null."""

    op: Literal["equal", "add", "remove"]
    text: str
    from_line: int | None
    to_line: int | None


class DiffOut(CamelModel):
    """The line diff between two revisions."""

    from_rev: int = Field(alias="from")
    to_rev: int = Field(alias="to")
    lines: list[DiffLine]
    added: int
    removed: int


class DocumentDraftIn(CamelModel):
    """Body of `PUT /documents/{id}/draft`."""

    body_md: str = Body
    title: str | None = Field(default=None, min_length=1, max_length=200)


class DocumentDraftOut(CamelModel):
    """The stored draft of one person."""

    base_rev: int
    body_md: str
    title: str | None
    updated_at: datetime
