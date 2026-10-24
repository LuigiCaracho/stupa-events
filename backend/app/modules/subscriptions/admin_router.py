"""Admin data request and erasure of one subscriber: `/api/admin/subscribers/{lookup,erase}`.

Both need `privacy.erase` and take the address in the body (a query string would land in
logs). The lookup answers the data request: what is stored and what Listmonk holds, never the
address or a token hash. The erasure calls `privacy_erase_subscriber`. Every call writes one
audit entry with `found` only, through the application connection; the subs role never writes
the audit chain.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import DbSession, Principal, require_principal
from app.modules.audit.service import record as audit_record
from app.modules.subscriptions import doi, emailkey
from app.modules.subscriptions.admin_schemas import (
    ExportListmonk,
    ExportOutbox,
    ExportProfile,
    SubscriberAddressIn,
    SubscriberExportOut,
)
from app.modules.subscriptions.db import get_subs_sessions
from app.modules.subscriptions.listmonk_client import ListmonkClient, checked_base_url
from app.modules.subscriptions.listmonk_port import ListmonkError, ListmonkSubscriber
from app.modules.subscriptions.models import Outbox, Subscriber, SubscriptionProfile
from app.shared.antiabuse import SettingsDep
from app.shared.errors import NotFoundError, ProblemDetail, ServiceUnavailableError

router = APIRouter(prefix="/admin/subscribers", tags=["admin"])
SubsSessions = Annotated[Callable[[], AsyncSession], Depends(get_subs_sessions)]
Admin = Annotated[Principal, Depends(require_principal("privacy.erase"))]
ListmonkFinder = Callable[[str], Awaitable[ListmonkSubscriber | None]]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}


def listmonk_finder(settings: SettingsDep) -> ListmonkFinder:
    """Return a lookup in Listmonk (a no-op that finds nothing while Listmonk is not set)."""

    async def find(canonical: str) -> ListmonkSubscriber | None:
        if not settings.listmonk_enabled:
            raise ListmonkError("not_configured", retryable=False)
        assert settings.listmonk_url and settings.listmonk_api_user and settings.listmonk_api_token
        url = checked_base_url(
            settings.listmonk_url,
            settings.listmonk_allowed_hosts,
            development=settings.environment == "development",
        )
        client = ListmonkClient(url, settings.listmonk_api_user, settings.listmonk_api_token)
        try:
            return await client.find_subscriber(canonical)
        finally:
            await client.aclose()

    return find


async def _listmonk(
    subs: AsyncSession, find: ListmonkFinder, canonical: str
) -> ExportListmonk | None:
    try:
        found = await find(canonical)
    except ListmonkError:
        return None
    if found is None:
        return ExportListmonk(present=False, lists=[])
    keys = dict(
        (await subs.execute(text("SELECT listmonk_id, key FROM listmonk_list"))).tuples().all()
    )
    return ExportListmonk(present=True, lists=sorted(keys[i] for i in found.lists if i in keys))


async def _export(subs: AsyncSession, row: Subscriber) -> SubscriberExportOut:
    profile = (
        await subs.execute(
            select(SubscriptionProfile).where(SubscriptionProfile.subscriber_id == row.id)
        )
    ).scalar_one_or_none()
    queued = (
        (
            await subs.execute(
                select(Outbox).where(Outbox.subscriber_id == row.id).order_by(Outbox.created_at)
            )
        )
        .scalars()
        .all()
    )
    return SubscriberExportOut(
        found=True,
        status=row.status,
        created_at=row.created_at,
        consent_text_version=row.consent_text_version,
        consent_categories=list(row.consent_categories),
        consent_at=row.consent_at,
        confirmed_at=row.confirmed_at,
        unsubscribed_at=row.unsubscribed_at,
        profile=None
        if profile is None
        else ExportProfile(
            interests=list(profile.interests),
            categories=list(profile.categories),
            mail_enabled=profile.mail_enabled,
            created_at=profile.created_at,
            last_fetched_on=profile.last_fetched_on,
        ),
        outbox=[ExportOutbox(op=o.op, state=o.state, created_at=o.created_at) for o in queued],
    )


def _require_keys(settings: SettingsDep) -> None:
    if not settings.subs_keys_enabled:
        raise ServiceUnavailableError("Mail subscriptions are not configured.")


async def _locate(
    subs: AsyncSession, settings: SettingsDep, address: str
) -> tuple[str, Subscriber | None]:
    assert settings.email_hash_key is not None
    canonical = doi.canonical_or_422(address)
    digest = emailkey.identity_hmac(settings.email_hash_key, canonical)
    row = (
        await subs.execute(select(Subscriber).where(Subscriber.email_hmac == digest))
    ).scalar_one_or_none()
    return canonical, row


@router.post(
    "/lookup",
    response_model=SubscriberExportOut,
    responses={422: _PROBLEM, 503: _PROBLEM},
)
async def lookup(
    body: SubscriberAddressIn,
    principal: Admin,
    settings: SettingsDep,
    sessions: SubsSessions,
    db: DbSession,
    find: Annotated[ListmonkFinder, Depends(listmonk_finder)],
) -> SubscriberExportOut:
    """Answer a data request for one address."""
    _require_keys(settings)
    out = SubscriberExportOut(found=False)
    async with sessions() as subs:
        canonical, row = await _locate(subs, settings, body.email)
        if row is not None:
            out = (await _export(subs, row)).model_copy(
                update={"listmonk": await _listmonk(subs, find, canonical)}
            )
    await audit_record(
        db,
        actor=principal.sub,
        action="subscriber.lookup",
        target_type="subscriber",
        data={"found": out.found},
    )
    await db.commit()
    return out


@router.post(
    "/erase",
    status_code=204,
    responses={404: _PROBLEM, 422: _PROBLEM, 503: _PROBLEM},
)
async def erase(
    body: SubscriberAddressIn,
    principal: Admin,
    settings: SettingsDep,
    sessions: SubsSessions,
    db: DbSession,
) -> Response:
    """Erase the subscriber, the profile and the tokens of one address."""
    _require_keys(settings)
    async with sessions() as subs:
        _, row = await _locate(subs, settings, body.email)
        found = row is not None
        if row is not None:
            await subs.execute(text("SELECT privacy_erase_subscriber(:id)"), {"id": row.id})
            await subs.commit()
    await audit_record(
        db,
        actor=principal.sub,
        action="subscriber.erase",
        target_type="subscriber",
        data={"found": found},
    )
    await db.commit()
    if not found:
        raise NotFoundError("Keine Daten zu dieser Adresse.", code="not_found")
    return Response(status_code=204)
