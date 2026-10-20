"""Schemas of the dossier API: attachments and the poster upload form (camelCase on the wire)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.modules.auth.schemas import CamelModel
from app.modules.files.models import Attachment

ScanStatus = Literal["pending", "clean", "infected", "error"]
AttachmentKind = Literal[
    "poster", "social_post", "business_plan", "quote", "contract", "howto_file", "other"
]
Visibility = Literal["team", "org", "shared"]
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
    """An attachment as the API shows it."""

    id: UUID
    event_id: UUID
    kind: AttachmentKind
    display_name: str
    mime: str
    size_bytes: int
    sha256: str
    visibility: Visibility
    scan_status: ScanStatus
    alt_text: str | None
    credit: str | None
    rights_basis: RightsBasis
    license_ref: str | None
    source_url: str | None
    persons_depicted: bool
    consent_note: str | None
    contains_date: bool
    dated_for: date | None
    meta: dict
    derivatives: DerivativesOut | None
    supersedes_id: UUID | None
    replaced_by: UUID | None = None
    retired_at: datetime | None
    created_at: datetime
    has_preview: bool


class AttachmentPatch(CamelModel):
    """Changeable fields of an attachment (`PATCH /attachments/{id}`)."""

    visibility: Visibility | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    alt_text: str | None = Field(default=None, max_length=250)
    credit: str | None = Field(default=None, max_length=200)
    rights_basis: RightsBasis | None = None
    license_ref: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)
    persons_depicted: bool | None = None
    consent_note: str | None = Field(default=None, max_length=500)
    contains_date: bool | None = None
    dated_for: date | None = None
    meta: dict | None = None


class PosterMeta(CamelModel):
    """The text fields of the poster upload (the file comes as multipart)."""

    alt_text: str = Field(min_length=1, max_length=250)
    credit: str = Field(min_length=1, max_length=200)
    rights_basis: RightsBasis
    persons_depicted: bool = False
    consent_note: str | None = Field(default=None, max_length=500)


def derivatives_out(raw: dict | None) -> DerivativesOut | None:
    """Map the stored derivative JSON (`thumb_400` ...) to the wire shape."""
    if not raw or not all(key in raw for key in VARIANT_KEYS.values()):
        return None
    return DerivativesOut(**{wire: raw[stored] for wire, stored in VARIANT_KEYS.items()})


def attachment_out(row: Attachment, replaced_by: UUID | None = None) -> AttachmentOut:
    """Build the wire shape of an attachment row."""
    return AttachmentOut(
        id=row.id,
        event_id=row.event_id,
        kind=row.kind,  # type: ignore[arg-type]
        display_name=row.display_name,
        mime=row.mime,
        size_bytes=row.size_bytes,
        sha256=row.sha256,
        visibility=row.visibility,  # type: ignore[arg-type]
        scan_status=row.scan_status,  # type: ignore[arg-type]
        alt_text=row.alt_text,
        credit=row.credit,
        rights_basis=row.rights_basis,  # type: ignore[arg-type]
        license_ref=row.license_ref,
        source_url=row.source_url,
        persons_depicted=row.persons_depicted,
        consent_note=row.consent_note,
        contains_date=row.contains_date,
        dated_for=row.dated_for,
        meta=row.meta or {},
        derivatives=derivatives_out(row.derivatives),
        supersedes_id=row.supersedes_id,
        replaced_by=replaced_by,
        retired_at=row.retired_at,
        created_at=row.created_at,
        has_preview=row.preview_key is not None,
    )
