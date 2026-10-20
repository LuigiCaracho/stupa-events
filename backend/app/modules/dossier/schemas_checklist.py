"""Wire shapes of the checklist."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field

from app.modules.auth.schemas import CamelModel

Phase = Literal["planning", "review", "live", "followup"]


class ChecklistItemOut(CamelModel):
    """One checklist item."""

    id: UUID
    text: str
    phase: Phase
    required: bool
    position: str
    assignee_sub: str | None
    assignee_name: str | None
    due_at: datetime | None
    due_offset_days: int | None
    due_manual: bool
    overdue: bool
    done_at: datetime | None
    done_by: str | None
    waived_reason: str | None
    from_template: bool


class TemplateRef(CamelModel):
    """The template a checklist resolves to."""

    slug: str
    name: str


class ChecklistOut(CamelModel):
    """The checklist of a dossier with the open required counts per phase."""

    items: list[ChecklistItemOut]
    open_required: dict[str, int]
    template: TemplateRef | None
    added: int | None = None


class ApplyTemplateIn(CamelModel):
    """Body of `apply-template`."""

    template_slug: str | None = Field(default=None, max_length=80)


class ChecklistItemCreate(CamelModel):
    """Body of `POST /events/{id}/checklist/items`."""

    text: str = Field(min_length=1, max_length=200)
    phase: Phase
    required: bool = False
    assignee_sub: str | None = Field(default=None, max_length=200)
    due_at: AwareDatetime | None = None


class ChecklistItemPatch(CamelModel):
    """Body of `PATCH /checklist-items/{id}`; `dueAt: null` hands the date back to the rule."""

    text: str | None = Field(default=None, min_length=1, max_length=200)
    phase: Phase | None = None
    required: bool | None = None
    assignee_sub: str | None = Field(default=None, max_length=200)
    due_at: AwareDatetime | None = None
    waived_reason: str | None = Field(default=None, max_length=500)
    position: str | None = Field(default=None, min_length=1, max_length=60)


class DoneIn(CamelModel):
    """Body of `done`."""

    done: bool
