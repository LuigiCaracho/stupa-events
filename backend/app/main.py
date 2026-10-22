"""FastAPI app factory.

`create_app()` wires settings, logging, middleware (trace id + security headers,
CORS off), the problem+json error contract, and all module routers under `/api`.
The uvicorn entrypoint runs with `--proxy-headers`.

Copied from STUPA-Workflow@93c33d6 backend/app/main.py (router list moved to api_routers)
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from app.api_routers import ROUTERS
from app.db import dispose_engine, get_sessionmaker
from app.logging_config import configure_logging
from app.middleware import (
    CsrfMiddleware,
    DefaultWriteRateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.modules.files.storage import build_object_storage
from app.modules.notifications.provider import close_mail_pool, create_mail_pool
from app.modules.publicapi.ics_router import router as ics_router
from app.modules.publicapi.shell.router import router as shell_router
from app.settings import Settings, get_settings
from app.shared.errors import register_exception_handlers, use_problem_json_contract

api_router = APIRouter(prefix="/api")


@api_router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    """Liveness endpoint (container healthcheck)."""
    return {"status": "ok"}


for _router in ROUTERS:
    api_router.include_router(_router)


async def _bootstrap_admins_on_startup(settings: Settings) -> None:  # pragma: no cover
    """Flag the bootstrap admins that already exist on startup (best effort).

    Without bootstrap config, which is the normal case, it touches no database. It
    logs a warning and never raises, because app startup must not fail here.
    """
    if not (settings.bootstrap_admin_subject_set or settings.bootstrap_admin_email_set):
        return
    from app.modules.auth.bootstrap import ensure_bootstrap_admins

    try:
        async with get_sessionmaker()() as db:
            await ensure_bootstrap_admins(db, settings)
            await db.commit()
    except Exception:  # noqa: BLE001 — startup must never fail on bootstrap
        logging.getLogger("app.auth.bootstrap").warning(
            "bootstrap admin startup sweep skipped (db unavailable?)", exc_info=True
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the arq pool and the object storage; release them on shutdown."""
    settings = get_settings()
    app.state.arq_pool = await create_mail_pool(settings.redis_url, settings.arq_queue_name)
    app.state.object_storage = build_object_storage(settings)
    await _bootstrap_admins_on_startup(settings)
    try:
        yield
    finally:
        await dispose_engine()
        await close_mail_pool(getattr(app.state, "arq_pool", None))
        redis_client = getattr(app.state, "_antiabuse_redis", None)
        if redis_client is not None:
            await redis_client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the application with middleware, error contract and routers."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)

    # CORS stays unregistered on purpose: no cross-origin access. The last middleware
    # added becomes the outermost one: SecurityHeaders, then the trace id, then CSRF,
    # and innermost the default write rate limit.
    app.add_middleware(DefaultWriteRateLimitMiddleware, settings=settings)
    app.add_middleware(CsrfMiddleware, settings=settings)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router)
    app.include_router(ics_router)
    app.include_router(shell_router)
    use_problem_json_contract(app)
    return app


app = create_app()
