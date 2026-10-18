"""Schemas of the dossier API: the poster attachment (camelCase on the wire)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.modules.auth.schemas import CamelModel
from app.modules.files.models import Attachment

ScanStatus = Literal["pending", "clean", "infected", "error"]
RightsBasis = Literal["own_work", "permission", "license", "partner_agreement", "unknown"]
PosterVariant = Literal["thumb400", "card1200"]

VARIANT_KEYS: dict[str, str] = {
    "thumb400": "thumb_400",
    "card1200": "card_1200",
    "og1200x630": "og_1200x630",
}


class DerivativeOut(CamelModel):
    """One WebP derivative: its public id and its size."""

    id: str
    width: int
    height: int


class DerivativesOut(CamelModel):
    """The derivatives of a clean poster."""

    thumb400: DerivativeOut
    card1200: DerivativeOut
    og1200x630: DerivativeOut = Field(alias="og1200x630")


class AttachmentOut(CamelModel):
    """A poster attachment as the API shows it."""

    id: UUID
    event_id: UUID
    kind: Literal["poster"]
    display_name: str
    mime: str
    size_bytes: int
    sha256: str
    scan_status: ScanStatus
    alt_text: str | None
    credit: str | None
    rights_basis: RightsBasis
    derivatives: DerivativesOut | None
    supersedes_id: UUID | None
    created_at: datetime


class PosterMeta(CamelModel):
    """The text fields of the poster upload (the file comes as multipart)."""

    alt_text: str = Field(min_length=1, max_length=250)
    credit: str = Field(min_length=1, max_length=200)
    rights_basis: RightsBasis


def derivatives_out(raw: dict | None) -> DerivativesOut | None:
    """Map the stored derivative JSON (`thumb_400` ...) to the wire shape."""
    if not raw or not all(key in raw for key in VARIANT_KEYS.values()):
        return None
    return DerivativesOut(**{wire: raw[stored] for wire, stored in VARIANT_KEYS.items()})


def attachment_out(row: Attachment) -> AttachmentOut:
    """Build the wire shape of an attachment row."""
    return AttachmentOut(
        id=row.id,
        event_id=row.event_id,
        kind="poster",
        display_name=row.display_name,
        mime=row.mime,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        scan_status=row.scan_status,  # type: ignore[arg-type]
        alt_text=row.alt_text,
        credit=row.credit,
        rights_basis=row.rights_basis,  # type: ignore[arg-type]
        derivatives=derivatives_out(row.derivatives),
        supersedes_id=row.supersedes_id,
        created_at=row.created_at,
    )
