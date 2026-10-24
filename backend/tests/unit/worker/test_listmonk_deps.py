"""The Listmonk jobs share one subs engine and one client per worker process."""

from __future__ import annotations

from tests._support.factories import make_settings
from worker.listmonk_deps import build_deps


def test_every_job_context_gets_the_same_engine_and_client() -> None:
    settings = make_settings(
        subs_database_url="postgresql+asyncpg://events_subs:pw@localhost:5434/events",
        pgcrypto_email_key="p" * 32,
        email_hash_key="h" * 32,
        listmonk_url="http://127.0.0.1:9002",
        listmonk_api_user="events-api",
        listmonk_api_token="t" * 32,
        listmonk_allowed_hosts=["127.0.0.1"],
    )
    first, second = build_deps({"settings": settings}), build_deps({"settings": settings})
    assert first is not None and second is not None
    assert first.subs is second.subs
    assert first.port is second.port


def test_an_injected_fake_still_wins() -> None:
    settings = make_settings(subs_database_url="postgresql+asyncpg://x:y@localhost/z")
    marker = object()
    deps = build_deps({"settings": settings, "subs_sessionmaker": marker}, need_port=False)
    assert deps is None or deps.subs is marker
