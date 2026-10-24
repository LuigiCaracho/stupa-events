"""Digest release and the subscription counters of the status page (I25).

`GET /api/admin/digests` lists the weekly drafts and `POST /api/admin/digests/{id}/release`
starts one campaign (right `digest.release`); the guard in `digest_release` refuses while the
breaker is open or the Listmonk count differs from ours. `GET /api/admin/subscriptions/status`
(right `subscriber.stats`) shows the outbox backlog, the breaker and the last reconcile. No
route returns an address.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.deps import Principal, require_principal
from app.modules.subscriptions.admin_schemas import DigestRunOut, SubscriptionStatusOut
from app.modules.subscriptions.db import get_subs_maker
from app.modules.subscriptions.digest_release import ReleaseBlockedError, release_digest
from app.modules.subscriptions.listmonk_client import client_from_settings
from app.modules.subscriptions.listmonk_port import ListmonkError, ListmonkPort
from app.modules.subscriptions.models import DigestRun
from app.modules.subscriptions.outbox import BREAKER_KEY
from app.modules.subscriptions.outbox_status import last_reconcile, outbox_status
from app.shared.antiabuse import SettingsDep
from app.shared.errors import ConflictError, ProblemDetail, ServiceUnavailableError

router = APIRouter(prefix="/admin", tags=["admin"])
Releaser = Annotated[Principal, Depends(require_principal("digest.release"))]
Viewer = Annotated[Principal, Depends(require_principal("subscriber.stats"))]
_PROBLEM: dict[str, Any] = {"model": ProblemDetail}
_RECENT = 60


async def listmonk_port(settings: SettingsDep) -> AsyncIterator[ListmonkPort]:
    """Yield the Listmonk client of the settings; 503 while Listmonk is not configured."""
    try:
        client = client_from_settings(settings)
    except ListmonkError:
        raise ServiceUnavailableError("Listmonk is not configured.") from None
    try:
        yield client
    finally:
        await client.aclose()


Maker = Annotated[async_sessionmaker[AsyncSession], Depends(get_subs_maker)]
Port = Annotated[ListmonkPort, Depends(listmonk_port)]


def _redis(request: Request) -> Any:
    return getattr(request.app.state, "arq_pool", None)


@router.get("/digests", response_model=list[DigestRunOut], responses={503: _PROBLEM})
async def list_digests(_: Releaser, maker: Maker) -> list[DigestRunOut]:
    """List the newest digest runs, drafts first."""
    async with maker() as session:
        rows = (
            await session.scalars(
                select(DigestRun)
                .order_by(DigestRun.week_start.desc(), DigestRun.list_key)
                .limit(_RECENT)
            )
        ).all()
    return [
        DigestRunOut(
            id=r.id,
            week_start=r.week_start,
            list_key=r.list_key,
            status=r.status,
            event_count=r.event_count,
            campaign_id=r.campaign_id,
            released_at=r.released_at,
        )
        for r in sorted(rows, key=lambda r: r.status != "draft")
    ]


@router.post(
    "/digests/{run_id}/release",
    status_code=204,
    responses={409: _PROBLEM, 503: _PROBLEM},
)
async def release(
    run_id: uuid.UUID, principal: Releaser, maker: Maker, port: Port, request: Request
) -> Response:
    """Start the campaign of one draft; refused with a code while the guard says no."""
    try:
        await release_digest(maker, port, run_id, by_sub=principal.sub, breaker=_redis(request))
    except ReleaseBlockedError as blocked:
        detail = "Der Digest kann nicht freigegeben werden."
        raise ConflictError(detail, code=blocked.code) from None
    except ListmonkError:
        detail = "Listmonk is unavailable."
        raise ServiceUnavailableError(detail, code="listmonk_unavailable") from None
    return Response(status_code=204)


@router.get(
    "/subscriptions/status", response_model=SubscriptionStatusOut, responses={503: _PROBLEM}
)
async def subscription_status(_: Viewer, maker: Maker, request: Request) -> SubscriptionStatusOut:
    """Return the outbox backlog, the breaker and the counters of the last reconcile."""
    counters = await outbox_status(maker)
    redis = _redis(request)
    breaker = bool(redis is not None and await redis.exists(BREAKER_KEY))
    return SubscriptionStatusOut(
        outbox_pending=counters.outbox_pending,
        outbox_dead=counters.outbox_dead,
        outbox_dead_deletes=counters.outbox_dead_deletes,
        outbox_lag_seconds=counters.outbox_lag_seconds,
        breaker_open=breaker,
        last_reconcile=await last_reconcile(redis) if redis is not None else None,
    )
