"""Comparison quotes of a dossier: groups, one selected quote per group, hidden not deleted.

Only roles that edit the dossier or read restricted material see them: a reader of the same
organization without the right gets 403 (no amounts in the body), a reader of another
organization gets 404 like for the dossier. The amounts live here and nowhere else: not in
`EventOut`, revisions, cards, the feed, notifications or the audit log. The selected total
is a suggestion for the budget; the server never writes `facts.budget_cents`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.actions import AuditAction
from app.modules.audit.service import record as audit_record
from app.modules.auth.principal import Principal
from app.modules.dossier.models_quotes import Quote
from app.modules.dossier.rules import ensure_permission, load_readable
from app.modules.dossier.schemas_quotes import (
    CurrencyTotal,
    QuoteCreate,
    QuoteGroupOut,
    QuoteOut,
    QuotePatch,
    QuotesOut,
)
from app.modules.events.models import Event
from app.modules.files.access import restricted_allowed
from app.modules.files.models import Attachment
from app.shared.errors import (
    ConflictError,
    FieldError,
    ForbiddenError,
    NotFoundError,
    ValidationProblem,
)
from app.shared.timeutil import DEFAULT_TZID, utcnow

MAIN_CURRENCY = "EUR"


def _today() -> date:
    return utcnow().astimezone(ZoneInfo(DEFAULT_TZID)).date()


def _out(row: Quote, today: date) -> QuoteOut:
    return QuoteOut(
        id=row.id,
        grp=row.grp,
        vendor=row.vendor,
        amount_cents=row.amount_cents,
        currency=row.currency,
        valid_until=row.valid_until,
        selected=row.selected,
        note=row.note,
        attachment_id=row.attachment_id,
        expired=row.valid_until is not None and row.valid_until < today,
        retired_at=row.retired_at,
        created_at=row.created_at,
    )


async def _readable_event(session: AsyncSession, principal: Principal, event_id: UUID) -> Event:
    event = await load_readable(session, principal, event_id)
    if not restricted_allowed(principal, event.organization_id):
        raise ForbiddenError("Missing permission to see quotes.")
    return event


async def list_quotes(
    session: AsyncSession, principal: Principal, event_id: UUID, *, include_retired: bool
) -> QuotesOut:
    """Return the quotes grouped, with cheapest, selected and the selected totals."""
    event = await _readable_event(session, principal, event_id)
    query = select(Quote).where(Quote.event_id == event.id)
    if not include_retired:
        query = query.where(Quote.retired_at.is_(None))
    rows = list(
        await session.scalars(query.order_by(Quote.grp, Quote.amount_cents, Quote.created_at))
    )
    today = _today()
    grouped: dict[str, list[Quote]] = defaultdict(list)
    for row in rows:
        grouped[row.grp].append(row)
    groups = []
    totals: dict[str, int] = defaultdict(int)
    for grp, quotes in grouped.items():
        live = [q for q in quotes if q.retired_at is None]
        cheapest = min(
            (q for q in live if q.currency == MAIN_CURRENCY and not _out(q, today).expired),
            key=lambda q: q.amount_cents,
            default=None,
        )
        chosen = next((q for q in live if q.selected), None)
        if chosen is not None:
            totals[chosen.currency] += chosen.amount_cents
        groups.append(
            QuoteGroupOut(
                grp=grp,
                quotes=[_out(q, today) for q in quotes],
                cheapest_id=cheapest.id if cheapest else None,
                selected_id=chosen.id if chosen else None,
            )
        )
    main = totals.pop(MAIN_CURRENCY, 0)
    return QuotesOut(
        groups=groups,
        selected_total_cents=main,
        selected_total_currency=MAIN_CURRENCY,
        suggested_budget_cents=main,
        other_currencies=[
            CurrencyTotal(currency=c, total_cents=t) for c, t in sorted(totals.items())
        ],
    )


async def _check_attachment(
    session: AsyncSession, event: Event, attachment_id: UUID | None
) -> None:
    if attachment_id is None:
        return
    row = await session.get(Attachment, attachment_id)
    if row is None or row.event_id != event.id or row.kind != "quote":
        raise ValidationProblem(
            "The file must be a quote file of this dossier.",
            errors=[FieldError(field="attachmentId", msg="not a quote file of this dossier")],
        )


async def _audit(
    session: AsyncSession, principal: Principal, event: Event, change: str, quote_id: UUID
) -> None:
    await audit_record(
        session,
        actor=principal.sub,
        action=AuditAction.QUOTE_CHANGE,
        target_type="event",
        target_id=str(event.id),
        data={"change": change, "quoteId": str(quote_id)},
    )


async def create(
    session: AsyncSession, principal: Principal, event_id: UUID, body: QuoteCreate
) -> QuoteOut:
    """Add a quote (no commit)."""
    event = await load_readable(session, principal, event_id)
    if not restricted_allowed(principal, event.organization_id):
        raise ForbiddenError("Missing permission to see quotes.")
    ensure_permission(principal, event, "dossier.attach")
    await _check_attachment(session, event, body.attachment_id)
    row = Quote(
        event_id=event.id,
        grp=body.grp.strip(),
        vendor=body.vendor.strip(),
        amount_cents=body.amount_cents,
        currency=body.currency,
        valid_until=body.valid_until,
        note=body.note,
        attachment_id=body.attachment_id,
        created_by=principal.sub,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    await _audit(session, principal, event, "create", row.id)
    return _out(row, _today())


async def _load(session: AsyncSession, principal: Principal, quote_id: UUID) -> tuple[Quote, Event]:
    row = await session.get(Quote, quote_id, with_for_update=True)
    if row is None:
        raise NotFoundError("quote not found")
    try:
        event = await _readable_event(session, principal, row.event_id)
    except NotFoundError:
        raise NotFoundError("quote not found") from None
    ensure_permission(principal, event, "dossier.attach")
    return row, event


async def patch(
    session: AsyncSession, principal: Principal, quote_id: UUID, body: QuotePatch
) -> QuoteOut:
    """Change fields of a quote; the selection goes through `select`."""
    row, event = await _load(session, principal, quote_id)
    values: dict[str, Any] = body.model_dump(exclude_unset=True)
    await _check_attachment(session, event, values.get("attachment_id"))
    if "grp" in values and values["grp"] != row.grp and row.selected:
        row.selected = False
    for name, value in values.items():
        setattr(
            row,
            name,
            value.strip() if isinstance(value, str) and name in ("grp", "vendor") else value,
        )
    row.updated_at = utcnow()
    await session.flush()
    await _audit(session, principal, event, "patch", row.id)
    return _out(row, _today())


async def _lock_group(session: AsyncSession, quote_id: UUID) -> None:
    head = (
        await session.execute(select(Quote.event_id, Quote.grp).where(Quote.id == quote_id))
    ).first()
    if head is None:
        raise NotFoundError("quote not found")
    key = func.hashtextextended(f"quote:{head.event_id}:{head.grp}", 0)
    await session.execute(select(func.pg_advisory_xact_lock(key)))


async def select_quote(session: AsyncSession, principal: Principal, quote_id: UUID) -> QuoteOut:
    """Select a quote and deselect the others of its group in one transaction.

    A transaction lock per event and group comes first, so two parallel selections run one
    after the other instead of both passing the deselect and then breaking `uq_quote_selected`.
    """
    await _lock_group(session, quote_id)
    row, event = await _load(session, principal, quote_id)
    if row.retired_at is not None:
        raise ConflictError("A hidden quote cannot be selected.", code="conflict")
    if row.valid_until is not None and row.valid_until < _today():
        raise ConflictError("The quote has expired.", code="quote_expired")
    await session.execute(
        update(Quote)
        .where(Quote.event_id == event.id, Quote.grp == row.grp, Quote.id != row.id, Quote.selected)
        .values(selected=False, updated_at=utcnow())
    )
    row.selected, row.updated_at = True, utcnow()
    await session.flush()
    await _audit(session, principal, event, "select", row.id)
    return _out(row, _today())


async def retire(session: AsyncSession, principal: Principal, quote_id: UUID) -> None:
    """Hide a quote (and drop its selection); there is no delete."""
    row, event = await _load(session, principal, quote_id)
    row.retired_at, row.selected, row.updated_at = utcnow(), False, utcnow()
    await session.flush()
    await _audit(session, principal, event, "retire", row.id)
