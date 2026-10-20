"""Wire shapes of comments and their anchors."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from app.modules.auth.schemas import CamelModel


class CommentOut(CamelModel):
    """A comment or reply."""

    id: UUID
    author_sub: str
    author_name: str | None
    actor_type: str
    body_md: str
    anchor: dict[str, Any] | None
    parent_id: UUID | None
    resolved_at: datetime | None
    resolved_by: str | None
    created_at: datetime


class ThreadOut(CommentOut):
    """A root comment with its replies, oldest first."""

    replies: list[CommentOut] = Field(default_factory=list)


class CommentCreate(CamelModel):
    """Body of `POST /events/{id}/comments`."""

    body_md: str = Field(min_length=1, max_length=4000)
    anchor: dict[str, Any] | None = None
    parent_id: UUID | None = None
