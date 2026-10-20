"""Upload, replace, change and hide the attachments of a dossier (M4 contract 3 and 5.1).

`create` is the one write path: it checks the right and the state, validates the bytes by
sniffing, re-encodes images (no EXIF, no original is ever stored), stores the object and
inserts the row in `pending`. The router commits, then queues the ClamAV scan. A poster in
`idea`, `planning` and `in_review` becomes the hero at once; in `approved` and `live` the
worker job `promote_poster` swaps it after scan and derivatives, so the published poster
never changes to an unscanned file. Files are never deleted, only hidden (`retired_at`).
"""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import threading
import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Final
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.auth.principal import Principal
from app.modules.dossier.rules import ensure_open, ensure_permission, load_readable
from app.modules.events import revisions
from app.modules.events.access import poster_of
from app.modules.events.models import Event
from app.modules.events.states import EventState
from app.modules.files.access import attachment_readable, readable_clause
from app.modules.files.attachment_meta import parse_meta
from app.modules.files.attachment_types import ATTACHMENT_IMAGE_MIMES, check_attachment
from app.modules.files.mime import file_extension
from app.modules.files.models import RESTRICTED_KINDS, Attachment
from app.modules.files.storage import ObjectStorage, StorageError
from app.modules.media.images import CleanImage, ImageRejected, clean_image
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    ServiceUnavailableError,
    ValidationProblem,
)
from app.shared.filenames import sanitize_display_name, sanitize_storage_name
from app.shared.timeutil import utcnow

MIN_POSTER_EDGE: Final[int] = 1200
STALE_PENDING: Final = timedelta(minutes=10)
CLEAN_CONCURRENCY: Final[int] = 2
_clean_threads: Final = threading.BoundedSemaphore(CLEAN_CONCURRENCY)
_clean_slots: Final = asyncio.Semaphore(CLEAN_CONCURRENCY)
_PRE_REVIEW = frozenset({EventState.IDEA.value, EventState.PLANNING.value})
_PUBLISHED = frozenset({EventState.APPROVED.value, EventState.LIVE.value})
_PATCH_FIELDS = (
    "display_name",
    "alt_text",
    "credit",
    "rights_basis",
    "license_ref",
    "source_url",
    "persons_depicted",
    "consent_note",
    "contains_date",
    "dated_for",
)


@dataclass(frozen=True, slots=True)
class NewAttachment:
    """The upload as the router parsed it (bytes plus the form fields)."""

    kind: str
    filename: str | None
    data: bytes
    visibility: str | None = None
    alt_text: str | None = None
    credit: str | None = None
    rights_basis: str = "unknown"
    license_ref: str | None = None
    source_url: str | None = None
    persons_depicted: bool | None = None
    consent_note: str | None = None
    contains_date: bool = False
    dated_for: date | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def _clean_bounded(data: bytes) -> CleanImage:
    with _clean_threads:
        return clean_image(data, ATTACHMENT_IMAGE_MIMES)


def _rejection(exc: ImageRejected) -> ValidationProblem:
    text = str(exc)
    reason = (
        "too_many_pixels"
        if "pixels" in text or "Bomb" in text or "frames" in text
        else "format_mismatch"
        if "not allowed" in text
        else "decode_failed"
    )
    return ValidationProblem(
        "The image was rejected.", code="image_rejected", extensions={"reason": reason}
    )


def check_consent(persons_depicted: bool | None, consent_note: str | None) -> None:
    """Persons on a picture need a consent note (422 `consent_missing`)."""
    if persons_depicted and not (consent_note or "").strip():
        raise ValidationProblem(
            "Persons are depicted: a consent note is required.",
            code="consent_missing",
            errors=[FieldError(field="consentNote", msg="required")],
        )


def authorize_attach(principal: Principal, event: Event, kind: str) -> None:
    """Check the right to attach a file of `kind` in the current state.

    Posters follow M3: `idea` and `planning` by the creator or any attacher, `in_review`
    by approvers, `approved` by approvers and `live` by `event.edit_critical_live`. Other
    kinds are open to every attacher until the dossier is closed.
    """
    ensure_permission(principal, event, "dossier.attach", own_only=True)
    if kind != "poster":
        ensure_open(event)
        return
    org_id = event.organization_id
    if event.state in _PRE_REVIEW:
        return
    needed = {
        EventState.IN_REVIEW.value: "event.approve",
        EventState.APPROVED.value: "event.approve",
        EventState.LIVE.value: "event.edit_critical_live",
    }.get(event.state)
    if needed is None:
        ensure_open(event)
        raise ConflictError("Field is locked in this state.", code="field_locked")
    if not principal.has(needed, org_id):
        raise ForbiddenError(f"Missing permission: {needed}")


def _visibility(new: NewAttachment) -> str:
    if new.kind in RESTRICTED_KINDS and new.visibility == "shared":
        raise ValidationProblem(
            "Vergleichsangebote können nicht für alle Mitglieder freigegeben werden.",
            code="visibility_not_allowed",
        )
    return new.visibility or ("shared" if new.kind == "howto_file" else "org")


def _check_social(kind: str, meta: dict[str, Any], mime: str, rights_ok: list[str]) -> None:
    if kind != "social_post" or meta.get("status") != "planned":
        return
    if not mime.startswith("image/"):
        raise ValidationProblem("Kein Foto, kein Post.", code="social_post_needs_image")
    if rights_ok:
        raise ValidationProblem(
            "The rights of the picture are incomplete.",
            code="rights_incomplete",
            errors=[FieldError(field=name, msg="required") for name in rights_ok],
        )


def missing_rights(row: Attachment | NewAttachment) -> list[str]:
    """Name the rights fields a picture still lacks (the four fields of `rightsComplete`)."""
    missing = []
    if not (row.alt_text or "").strip():
        missing.append("altText")
    if not (row.credit or "").strip():
        missing.append("credit")
    if row.rights_basis == "unknown":
        missing.append("rightsBasis")
    if row.persons_depicted and not (row.consent_note or "").strip():
        missing.append("consentNote")
    return missing


async def _store_image(new: NewAttachment) -> tuple[bytes, str, dict[str, Any]]:
    try:
        async with _clean_slots:
            image = await asyncio.to_thread(_clean_bounded, new.data)
    except ImageRejected as exc:
        raise _rejection(exc) from exc
    if len(image.data) > 10 * 1024 * 1024:
        raise PayloadTooLargeError(
            "The image exceeds 10 MiB.", code="file_too_large", extensions={"limitBytes": 10485760}
        )
    if new.kind == "poster" and max(image.width, image.height) < MIN_POSTER_EDGE:
        raise ValidationProblem(
            f"The poster needs at least {MIN_POSTER_EDGE} px on its long edge.",
            code="image_too_small",
        )
    return image.data, image.mime, {"width": image.width, "height": image.height}


async def create(
    session: AsyncSession,
    storage: ObjectStorage | None,
    principal: Principal,
    event_id: UUID,
    new: NewAttachment,
    *,
    supersedes: Attachment | None = None,
) -> Attachment:
    """Store an upload and insert its `pending` row (no commit, no scan).

    Raises:
        NotFoundError: The dossier is not readable.
        ForbiddenError, ConflictError: The right or the state forbids the upload.
        UnsupportedMediaTypeError, PayloadTooLargeError, ValidationProblem: Bad bytes or data.
        ServiceUnavailableError: The object storage is off or failed.
    """
    event = await load_readable(session, principal, event_id)
    authorize_attach(principal, event, new.kind)
    if storage is None:
        raise ServiceUnavailableError("Object storage unavailable.")
    checked = check_attachment(new.kind, new.filename, new.data)
    visibility = _visibility(new)
    check_consent(new.persons_depicted, new.consent_note)
    data, mime, dims = (new.data, checked.mime, {})
    if checked.is_image:
        data, mime, dims = await _store_image(new)
    meta = parse_meta(new.kind, {**new.meta, **(dims if new.kind == "poster" else {})})
    _check_social(new.kind, meta, mime, missing_rights(new))
    previous = await poster_of(session, event) if new.kind == "poster" else None
    attachment_id = uuid.uuid4()
    kind_dir = new.kind.replace("_", "-") if new.kind != "poster" else "poster"
    row = Attachment(
        id=attachment_id,
        event_id=event.id,
        kind=new.kind,
        storage_key=f"events/{event.id}/{kind_dir}/{attachment_id}",
        display_name=sanitize_display_name(new.filename),
        storage_name=sanitize_storage_name(new.filename),
        mime=mime,
        size_bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        alt_text=(new.alt_text or "").strip() or None,
        credit=(new.credit or "").strip() or None,
        rights_basis=new.rights_basis,
        license_ref=new.license_ref,
        source_url=new.source_url,
        persons_depicted=bool(new.persons_depicted),
        consent_note=(new.consent_note or "").strip() or None,
        visibility=visibility,
        contains_date=new.contains_date,
        dated_for=new.dated_for,
        meta=meta,
        supersedes_id=(supersedes.id if supersedes else previous.id if previous else None),
    )
    session.add(row)
    await session.flush()
    try:
        assert row.storage_key is not None
        await storage.put(row.storage_key, data, mime)
    except StorageError as exc:
        raise ServiceUnavailableError("Object storage write failed.") from exc
    try:
        await _finish(session, principal, event, row, previous, supersedes)
    except BaseException:
        with contextlib.suppress(StorageError):
            await storage.remove(row.storage_key)
        raise
    return row


async def _finish(
    session: AsyncSession,
    principal: Principal,
    event: Event,
    row: Attachment,
    previous: Attachment | None,
    supersedes: Attachment | None,
) -> None:
    replaced = supersedes is not None or previous is not None
    action = AuditAction.ATTACHMENT_REPLACE if replaced else AuditAction.ATTACHMENT_UPLOAD
    data = {"attachmentId": str(row.id), "kind": row.kind}
    if row.kind == "poster" and event.state not in _PUBLISHED:
        for old in (previous, supersedes):
            if old is not None:
                old.retired_at = utcnow()
        updated = await _link_hero(session, event, row.id)
        await revisions.append_revision(
            session, updated, actor=principal.sub, field_class="dossier"
        )
        await revisions.audit(session, updated, actor=principal.sub, action=action, data=data)
        return
    await revisions.audit(session, event, actor=principal.sub, action=action, data=data)


async def _link_hero(session: AsyncSession, event: Event, attachment_id: UUID) -> Event:
    result = await session.execute(
        update(Event)
        .where(Event.id == event.id, Event.rev == event.rev)
        .values(hero_attachment_id=attachment_id, rev=Event.rev + 1)
        .returning(Event)
        .execution_options(populate_existing=True, synchronize_session=False)
    )
    updated = result.scalar_one_or_none()
    if updated is None:
        raise ConflictError("The dossier was changed in the meantime.")
    return updated


async def load_attachment(
    session: AsyncSession, principal: Principal, attachment_id: UUID
) -> tuple[Attachment, Event]:
    """Load an attachment the caller may read, with its dossier (404 otherwise)."""
    row = await session.get(Attachment, attachment_id)
    if row is None:
        raise NotFoundError("attachment not found")
    try:
        event = await load_readable(session, principal, row.event_id)
    except NotFoundError:
        raise NotFoundError("attachment not found") from None
    if not attachment_readable(principal, event.organization_id, row.kind, row.visibility):
        raise NotFoundError("attachment not found")
    return row, event


async def replace(
    session: AsyncSession,
    storage: ObjectStorage | None,
    principal: Principal,
    attachment_id: UUID,
    new: NewAttachment,
) -> Attachment:
    """Upload a new version of an attachment.

    The old row stays listed until the scan job found the new file clean (a poster before
    publication is swapped at once). `personsDepicted` carries over only when not sent.
    """
    old, event = await load_attachment(session, principal, attachment_id)
    persons = old.persons_depicted if new.persons_depicted is None else new.persons_depicted
    carried = NewAttachment(
        kind=old.kind,
        filename=new.filename,
        data=new.data,
        visibility=new.visibility or old.visibility,
        alt_text=new.alt_text if new.alt_text is not None else old.alt_text,
        credit=new.credit if new.credit is not None else old.credit,
        rights_basis=new.rights_basis if new.rights_basis != "unknown" else old.rights_basis,
        license_ref=new.license_ref if new.license_ref is not None else old.license_ref,
        source_url=new.source_url if new.source_url is not None else old.source_url,
        persons_depicted=persons,
        consent_note=new.consent_note
        if new.consent_note is not None
        else old.consent_note
        if persons
        else None,
        contains_date=new.contains_date,
        dated_for=new.dated_for,
        meta=new.meta
        or {k: v for k, v in (old.meta or {}).items() if k not in ("width", "height")},
    )
    return await create(session, storage, principal, event.id, carried, supersedes=old)


async def patch(
    session: AsyncSession, principal: Principal, attachment_id: UUID, changes: dict[str, Any]
) -> Attachment:
    """Change visibility, name, rights fields or meta of an attachment (last writer wins)."""
    row, event = await load_attachment(session, principal, attachment_id)
    ensure_permission(principal, event, "dossier.attach", own_only=False)
    ensure_open(event)
    visibility = changes.get("visibility")
    if visibility == "shared" and row.kind in RESTRICTED_KINDS:
        raise ValidationProblem(
            "Vergleichsangebote können nicht für alle Mitglieder freigegeben werden.",
            code="visibility_not_allowed",
        )
    for name in _PATCH_FIELDS:
        if name in changes:
            value = changes[name]
            if name == "display_name":
                value = _renamed(row, value)
            setattr(row, name, value)
    if visibility is not None:
        row.visibility = visibility
    check_consent(row.persons_depicted, row.consent_note)
    if "meta" in changes and changes["meta"] is not None:
        row.meta = parse_meta(row.kind, {**changes["meta"], **_dims(row)})
        _check_social(row.kind, row.meta, row.mime, missing_rights(row))
    await _flush_or_conflict(session)
    await revisions.audit(
        session,
        event,
        actor=principal.sub,
        action=AuditAction.ATTACHMENT_UPDATE,
        data={"attachmentId": str(row.id), "fields": sorted(changes)},
    )
    return row


def _renamed(row: Attachment, name: str) -> str:
    cleaned = sanitize_display_name(name)
    if file_extension(cleaned) != file_extension(row.display_name):
        raise ValidationProblem(
            "A rename keeps the file extension.",
            code="extension_changed",
            errors=[FieldError(field="displayName", msg="extension must stay")],
        )
    return cleaned


def _dims(row: Attachment) -> dict[str, Any]:
    return {
        k: v
        for k, v in (row.meta or {}).items()
        if row.kind == "poster" and k in ("width", "height")
    }


def _raise_poster_in_use(exc: DBAPIError) -> None:
    if "poster of a published event" in str(exc):
        raise ConflictError(
            "The poster of a published dossier cannot be changed this way.", code="poster_in_use"
        ) from exc


async def _flush_or_conflict(session: AsyncSession) -> None:
    try:
        await session.flush()
    except DBAPIError as exc:
        _raise_poster_in_use(exc)
        if "ck_attachment_restricted_not_shared" in str(exc):
            raise ValidationProblem(
                "Vergleichsangebote können nicht für alle Mitglieder freigegeben werden.",
                code="visibility_not_allowed",
            ) from exc
        raise


async def retire(session: AsyncSession, principal: Principal, attachment_id: UUID) -> None:
    """Hide an attachment (409 `poster_in_use` for the live poster of a published dossier)."""
    row, event = await load_attachment(session, principal, attachment_id)
    ensure_permission(principal, event, "dossier.attach", own_only=False)
    ensure_open(event)
    if row.retired_at is not None:
        return
    row.retired_at = utcnow()
    await _flush_or_conflict(session)
    await revisions.audit(
        session,
        event,
        actor=principal.sub,
        action=AuditAction.ATTACHMENT_RETIRE,
        data={"attachmentId": str(row.id)},
    )


async def request_rescan(
    session: AsyncSession, principal: Principal, attachment_id: UUID
) -> Attachment:
    """Reset a failed or stuck scan to `pending` so that the caller can queue it again."""
    row, event = await load_attachment(session, principal, attachment_id)
    if not principal.has("event.approve", event.organization_id):
        raise ForbiddenError("Missing permission: event.approve")
    stuck = row.scan_status == "pending" and row.created_at < utcnow() - STALE_PENDING
    if row.scan_status != "error" and not stuck:
        raise ConflictError("Only a scan that failed can be repeated.", code="conflict")
    row.scan_status = "pending"
    await revisions.audit(
        session,
        event,
        actor=principal.sub,
        action=AuditAction.ATTACHMENT_RESCAN,
        data={"attachmentId": str(row.id)},
    )
    return row


async def list_attachments(
    session: AsyncSession,
    principal: Principal,
    event_id: UUID,
    *,
    kind: str | None = None,
    include_retired: bool = False,
) -> list[tuple[Attachment, UUID | None]]:
    """List the readable attachments of a dossier with the id of their successor.

    The visibility filter runs in SQL. Rows come newest first within a kind.
    """
    event = await load_readable(session, principal, event_id)
    query = select(Attachment).where(
        Attachment.event_id == event.id, readable_clause(principal, event.organization_id)
    )
    if kind is not None:
        query = query.where(Attachment.kind == kind)
    if not include_retired:
        query = query.where(Attachment.retired_at.is_(None))
    rows = list(
        await session.scalars(query.order_by(Attachment.kind, Attachment.created_at.desc()))
    )
    successors = {r.supersedes_id: r.id for r in rows if r.supersedes_id is not None}
    return [(r, successors.get(r.id)) for r in rows]
