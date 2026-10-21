"""Attachments: the ``attachment`` table (DDL in migrations ``0002`` and ``0005``).

One row holds one uploaded file of an event. The binary object lives in MinIO under
``storage_key``, never in the database. ``scan_status`` carries the ClamAV result: the
file stays ``pending`` and nobody can download it until the worker sets ``clean``. On a
finding the worker deletes the object, sets ``storage_key`` to NULL and writes the
signature into ``scan_result``.

The ORM class stays free of a foreign key to ``event`` on purpose, so the files module
does not depend on the events models. The migration declares ``event_id`` as a foreign
key. A file is never deleted: a replacement points to its predecessor through
``supersedes_id``, and ``retired_at`` hides a file.

Copied from STUPA-Workflow@93c33d6 backend/app/modules/files/models.py (event owner, rights columns)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, CreatedAtMixin, UUIDPkMixin

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024

ATTACHMENT_KINDS = (
    "poster",
    "social_post",
    "business_plan",
    "quote",
    "contract",
    "howto_file",
    "other",
)
RESTRICTED_KINDS = ("quote", "business_plan", "contract")
SCAN_STATUSES = ("pending", "clean", "infected", "error")
RIGHTS_BASES = ("own_work", "permission", "license", "partner_agreement", "unknown")
VISIBILITIES = ("team", "org", "shared")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Attachment(UUIDPkMixin, CreatedAtMixin, Base):
    """An attachment of an event, usually its poster.

    Attributes:
        storage_key: Object key in the attachment bucket. NULL after a finding.
        display_name: The cleaned original file name, for display and download.
        storage_name: ASCII-safe file name for the object and the download header.
        sha256: Hex digest of the stored bytes. The public media id derives from it.
        scan_status: ``pending``, ``clean``, ``infected`` or ``error``.
        scan_result: NULL, ``clean`` or the signature of the finding.
        derivatives: WebP derivatives in the public bucket, filled by the worker.
        supersedes_id: The file that this one replaced.
        retired_at: Set when the file is hidden; the row stays.
    """

    __tablename__ = "attachment"

    event_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    kind: Mapped[str] = mapped_column(Text, server_default="poster", default="poster")
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str] = mapped_column(Text)
    storage_name: Mapped[str] = mapped_column(Text)
    mime: Mapped[str] = mapped_column(Text)
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(Text)
    scan_status: Mapped[str] = mapped_column(Text, server_default="pending", default="pending")
    scan_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    alt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit: Mapped[str | None] = mapped_column(Text, nullable=True)
    rights_basis: Mapped[str] = mapped_column(Text, server_default="unknown", default="unknown")
    license_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    persons_depicted: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    consent_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(Text, server_default="org", default="org")
    meta: Mapped[dict] = mapped_column(JSONB, server_default="{}", default=dict)
    derivatives: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attachment.id", ondelete="RESTRICT"), nullable=True
    )
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    contains_date: Mapped[bool] = mapped_column(Boolean, server_default="false", default=False)
    dated_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    preview_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            f"size_bytes <= CASE WHEN mime LIKE 'image/%' THEN {MAX_IMAGE_BYTES} "
            f"ELSE {MAX_DOCUMENT_BYTES} END",
            name="size",
        ),
        CheckConstraint(
            f"kind NOT IN ({', '.join(repr(k) for k in RESTRICTED_KINDS)}) "
            "OR visibility <> 'shared'",
            name="restricted_not_shared",
        ),
        Index(
            "ix_attachment_event_kind",
            "event_id",
            "kind",
            postgresql_where=text("retired_at IS NULL"),
        ),
        CheckConstraint(_in("kind", ATTACHMENT_KINDS), name="kind"),
        CheckConstraint(_in("scan_status", SCAN_STATUSES), name="scan_status"),
        CheckConstraint(_in("rights_basis", RIGHTS_BASES), name="rights_basis"),
        CheckConstraint(_in("visibility", VISIBILITIES), name="visibility"),
        Index("ix_attachment_event_id", "event_id"),
    )
