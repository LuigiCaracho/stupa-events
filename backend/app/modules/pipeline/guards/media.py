"""Guards on the poster: image, consent, quarantine and the reused flyer."""

from __future__ import annotations

from datetime import datetime

from app.modules.pipeline.reasons import FixAction, Reason, blocker
from app.modules.pipeline.snapshot import Actor, Snapshot


def image_or_exception(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `imageOrException`: a usable poster or a valid image exception (E41)."""
    if snapshot.image_exception_reason is not None:
        return []
    if snapshot.poster is not None and snapshot.poster.usable:
        return []
    return [blocker("image_required", field="poster", fix=FixAction.UPLOAD_POSTER)]


def rights_complete(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `rightsComplete`: depicted persons need a consent note when a poster counts."""
    poster = snapshot.poster
    if snapshot.image_exception_reason is not None or poster is None or poster.consent_ok:
        return []
    return [blocker("rights_incomplete", field="poster", fix=FixAction.FILL_RIGHTS)]


def attachments_scanned(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `attachmentsScanned`: no other visible attachment is unscanned or infected."""
    if snapshot.quarantined_attachments > 0:
        return [blocker("attachment_quarantined", field="attachments")]
    return []


def flyer_date_confirmed(snapshot: Snapshot, actor: Actor, now: datetime) -> list[Reason]:
    """Guard `flyerDateConfirmed`: a poster used in another year needs a fresh check."""
    poster = snapshot.poster
    if poster is None or not poster.reused_in_other_year:
        return []
    checked = snapshot.flyer_checked_at
    if checked is not None and poster.created_at is not None and checked >= poster.created_at:
        return []
    return [blocker("flyer_date", field="poster", fix=FixAction.CONFIRM_FLYER)]
