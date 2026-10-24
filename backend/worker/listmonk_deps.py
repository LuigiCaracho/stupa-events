"""Shared wiring of the Listmonk jobs: settings, the subs session factory and the client.

The jobs read everything from the arq `ctx` first, so tests inject fakes (`settings`,
`subs_sessionmaker`, `listmonk`). Without an injection the worker uses one engine of the role
`events_subs` per process (its own small pool, the role allows six connections for API and worker
together) and one HTTP client. arq hands every job a copy of the context, so they are cached here
and not in `ctx`: a new engine per job ran the role out of connections within minutes. A job that
finds Listmonk or the subs database unconfigured skips itself; a missing key is no crash.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
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


@lru_cache
def _shared_maker(url: str) -> Maker:
    engine = create_async_engine(url, pool_size=2, max_overflow=0, pool_pre_ping=True)
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@lru_cache
def _shared_client(base: str, user: str, token: str) -> ListmonkClient:
    return ListmonkClient(base, user, token)


def _subs_maker(ctx: dict[str, Any], settings: Settings) -> Maker | None:
    if (maker := ctx.get("subs_sessionmaker")) is not None:
        return maker
    if not settings.subs_database_url:
        return None
    return _shared_maker(settings.subs_database_url)


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
    return _shared_client(base, str(settings.listmonk_api_user), str(settings.listmonk_api_token))


def build_deps(ctx: dict[str, Any], *, need_port: bool = True) -> Deps | None:
    """Return the wiring, or None when the subs database, the key or Listmonk is not configured."""
    settings: Settings = ctx.get("settings") or load_settings()
    subs = _subs_maker(ctx, settings)
    port = _port(ctx, settings) if need_port else ctx.get("listmonk")
    if subs is None or not settings.pgcrypto_email_key or (need_port and port is None):
        return None
    app = ctx.get("app_sessionmaker") or get_sessionmaker()
    return Deps(settings, subs, app, port, settings.pgcrypto_email_key)  # type: ignore[arg-type]
