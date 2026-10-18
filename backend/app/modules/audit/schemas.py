"""API schemas for the audit module (read-only views).

The views emit ``hash`` and ``prevHash`` as hex. By contract, ``data`` carries only
id references and metadata.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/audit/schemas.py (read views only)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.audit.models import (
    AuditEntry,
    AuditVerification,
    ChainBreak,
    VerificationTrigger,
)


class _CamelModel(BaseModel):
    """Base model that emits camelCase JSON aliases and accepts field names."""

    model_config = ConfigDict(populate_by_name=True)


class AuditEntryOut(_CamelModel):
    """One audit entry (read view)."""

    id: int
    at: datetime
    actor: str | None
    action: str
    target_type: str | None = Field(alias="targetType")
    target_id: str | None = Field(alias="targetId")
    data: dict[str, Any]
    hash: str
    prev_hash: str | None = Field(alias="prevHash")

    @classmethod
    def from_entry(cls, entry: AuditEntry) -> AuditEntryOut:
        """Map an ORM row to the out schema and hex-encode the bytea hashes."""
        return cls(
            id=entry.id,
            at=entry.at,
            actor=entry.actor,
            action=entry.action,
            targetType=entry.target_type,
            targetId=entry.target_id,
            data=entry.data,
            hash=entry.hash.hex(),
            prevHash=entry.prev_hash.hex() if entry.prev_hash is not None else None,
        )


class AuditPageOut(_CamelModel):
    """Cursor-paged audit view, keyset on ``id`` descending, newest first.

    ``nextCursor`` holds the ``id`` for the next call, which you pass as the query
    parameter ``before``. At the end of the log it is ``None``.
    """

    items: list[AuditEntryOut]
    next_cursor: int | None = Field(default=None, alias="nextCursor")
    has_more: bool = Field(default=False, alias="hasMore")


class ChainVerificationOut(_CamelModel):
    """Result of chain verification (``/admin/audit/verify``)."""

    valid: bool
    checked: int
    broken_at: int | None = Field(default=None, alias="brokenAt")
    reason: str | None = None


class AuditVerificationOut(_CamelModel):
    """A stored chain check (``/admin/audit/verify``, ``/admin/audit/verify/latest``).

    ``trigger`` tells what started the check: the nightly ``cron``, a ``manual``
    call or a ``restore``. ``brokenAt`` and ``reason`` name the first break when
    ``valid`` is false.
    """

    id: UUID
    started_at: datetime = Field(alias="startedAt")
    finished_at: datetime | None = Field(default=None, alias="finishedAt")
    valid: bool
    checked: int
    broken_at: int | None = Field(default=None, alias="brokenAt")
    reason: ChainBreak | None = None
    trigger: VerificationTrigger
    triggered_by: str | None = Field(default=None, alias="triggeredBy")

    @classmethod
    def from_row(cls, row: AuditVerification) -> AuditVerificationOut:
        """Map a stored check to the out schema."""
        return cls(
            id=row.id,
            startedAt=row.started_at,
            finishedAt=row.finished_at,
            valid=row.valid,
            checked=row.checked,
            brokenAt=row.broken_at,
            reason=row.reason,  # pyright: ignore[reportArgumentType]  # DB CHECK limits it
            trigger=row.trigger,  # pyright: ignore[reportArgumentType]  # DB CHECK limits it
            triggeredBy=row.triggered_by,
        )
