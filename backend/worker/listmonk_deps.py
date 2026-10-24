"""Shared wiring of the Listmonk jobs: settings, the subs session factory and the client.

The jobs read everything from the arq `ctx` first, so tests inject fakes (`settings`,
`subs_sessionmaker`, `listmonk`). Without an injection the worker builds the engine of the role
`events_subs` (its own small pool, the role allows six connections for API and worker together)
and the HTTP client from the settings. A job that finds Listmonk or the subs database
unconfigured skips itself; a missing key is no crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db import get_sessionmaker
from app.modules.subscriptions.listmonk_client import ListmonkClient, checked_base_url
from app.modules.subscriptions.listmonk_port import ListmonkPort
from app.settings import Settings, load_settings

Maker = async_sessionmaker[AsyncSession]


@dataclass(frozen=True, slots=True)
class Deps:
    """Everything a Listmonk job needs."""

    settings: Settings
    subs: Maker
    app: Maker
    port: ListmonkPort
    email_key: str


def _subs_maker(ctx: dict[str, Any], settings: Settings) -> Maker | None:
    if (maker := ctx.get("subs_sessionmaker")) is not None:
        return maker
    if not settings.subs_database_url:
        return None
    engine = create_async_engine(settings.subs_database_url, pool_size=2, max_overflow=0)
    ctx["subs_sessionmaker"] = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    return ctx["subs_sessionmaker"]


def _port(ctx: dict[str, Any], settings: Settings) -> ListmonkPort | None:
    if (port := ctx.get("listmonk")) is not None:
        return port
    if not settings.listmonk_enabled:
        return None
    base = checked_base_url(
        str(settings.listmonk_url),
        settings.listmonk_allowed_hosts,
        development=not settings.is_production,
    )
    ctx["listmonk"] = ListmonkClient(
        base, str(settings.listmonk_api_user), str(settings.listmonk_api_token)
    )
    return ctx["listmonk"]


def build_deps(ctx: dict[str, Any], *, need_port: bool = True) -> Deps | None:
    """Return the wiring, or None when the subs database, the key or Listmonk is not configured."""
    settings: Settings = ctx.get("settings") or load_settings()
    subs = _subs_maker(ctx, settings)
    port = _port(ctx, settings) if need_port else ctx.get("listmonk")
    if subs is None or not settings.pgcrypto_email_key or (need_port and port is None):
        return None
    app = ctx.get("app_sessionmaker") or get_sessionmaker()
    return Deps(settings, subs, app, port, settings.pgcrypto_email_key)  # type: ignore[arg-type]
