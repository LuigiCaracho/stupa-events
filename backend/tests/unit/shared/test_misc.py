"""Small helpers: time, full-text search builder, models discovery, rate-limit dependencies."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import APIRouter, Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import column
from sqlalchemy.dialects import postgresql

from app import models
from app.shared import antiabuse, timeutil
from app.shared.ratelimit import InMemoryRateLimiter
from app.shared.search import fts_rank, trigram_rank
from tests._support.factories import make_principal, make_settings


def test_timeutil_requires_awareness() -> None:
    assert timeutil.utcnow().tzinfo is UTC
    naive = datetime(2026, 10, 25, 0, 30)
    for call in (timeutil.require_aware, timeutil.to_utc, timeutil.to_local):
        with pytest.raises(ValueError):
            call(naive)


def test_local_day_follows_berlin_wall_time() -> None:
    late = datetime(2026, 10, 24, 22, 30, tzinfo=UTC)
    assert timeutil.local_date_iso(late) == "2026-10-25"
    assert timeutil.to_local(late).hour == 0
    summer = datetime(2026, 3, 28, 23, 30, tzinfo=timezone(timedelta(hours=-5)))
    assert timeutil.to_utc(summer).hour == 4


def test_fts_rank_uses_the_unaccent_configuration() -> None:
    where, rank = fts_rank("Fachschaft Sitzung", column("tsv"))
    sql = str(where.compile(dialect=postgresql.dialect()))
    assert "@@ websearch_to_tsquery" in sql
    assert "ts_rank" in str(rank.compile(dialect=postgresql.dialect()))
    assert "de_unaccent" in str(where.compile(compile_kwargs={"literal_binds": True}))


def test_trigram_rank_falls_back_to_ilike_off_postgres() -> None:
    where, rank = trigram_rank("50%", [column("a"), column("b")], dialect="sqlite")
    assert "LIKE" in str(where).upper()
    assert str(rank.compile(compile_kwargs={"literal_binds": True})) == "0.0"
    pg_where, _ = trigram_rank("x", [column("a")])
    assert "word_similarity" in str(pg_where.compile(dialect=postgresql.dialect()))


def test_models_are_discovered_without_a_list() -> None:
    loaded = models.import_all_models()
    assert "app.modules.auth.models" in loaded
    assert {"principal", "auth_session", "audit_entry", "attachment", "markdown_image"} <= set(
        models.Base.metadata.tables
    )


def _upload_client(limiter: InMemoryRateLimiter, principal: object | None) -> TestClient:
    app = FastAPI()
    router = APIRouter()
    router.add_api_route(
        "/up",
        lambda: "ok",
        methods=["POST"],
        dependencies=[Depends(antiabuse.rate_limit_attachments)],
    )
    router.add_api_route(
        "/img",
        lambda: "ok",
        methods=["POST"],
        dependencies=[Depends(antiabuse.rate_limit_media_images)],
    )
    router.add_api_route(
        "/cap",
        lambda: "ok",
        methods=["POST"],
        dependencies=[Depends(antiabuse.enforce_attachment_body_cap)],
    )
    router.add_api_route(
        "/auth-cap",
        lambda: "ok",
        methods=["POST"],
        dependencies=[Depends(antiabuse.body_cap("rl_attachments_per_hour"))],
    )
    app.include_router(router)
    from app.deps import get_current_principal
    from app.settings import get_settings
    from app.shared.errors import register_exception_handlers

    register_exception_handlers(app)
    app.dependency_overrides[antiabuse.get_rate_limiter] = lambda: limiter
    app.dependency_overrides[get_current_principal] = lambda: principal
    app.dependency_overrides[get_settings] = lambda: make_settings(
        rl_attachments_per_hour=2, rl_media_images_per_hour=1, attachment_max_bytes=100
    )
    return TestClient(app)


def test_upload_limit_is_per_principal_with_retry_after() -> None:
    limiter = InMemoryRateLimiter()
    client = _upload_client(limiter, make_principal())
    assert [client.post("/up").status_code for _ in range(3)] == [200, 200, 429]
    blocked = client.post("/up")
    assert blocked.json()["code"] == "rate_limited" and int(blocked.headers["retry-after"]) > 0
    other = _upload_client(limiter, make_principal(sub="sub-2"))
    assert other.post("/up").status_code == 200


def test_anonymous_upload_is_keyed_by_ip_and_media_limit_skips_anonymous() -> None:
    client = _upload_client(InMemoryRateLimiter(), None)
    assert [client.post("/up").status_code for _ in range(3)] == [200, 200, 429]
    assert [client.post("/img").status_code for _ in range(3)] == [200, 200, 200]
    signed = _upload_client(InMemoryRateLimiter(), make_principal())
    assert [signed.post("/img").status_code for _ in range(2)] == [200, 429]


def test_body_caps_answer_413_on_content_length() -> None:
    client = _upload_client(InMemoryRateLimiter(), None)
    assert client.post("/cap", content=b"x" * 50).status_code == 200
    too_big = client.post("/cap", content=b"x" * (100 + 64 * 1024 + 1))
    assert too_big.status_code == 413 and too_big.json()["code"] == "payload_too_large"
    assert client.post("/auth-cap", content=b"x" * 3).status_code == 413


def test_client_ip_and_limiter_selection() -> None:
    assert (
        antiabuse.client_ip(SimpleNamespace(client=SimpleNamespace(host="10.0.0.1"))) == "10.0.0.1"
    )  # type: ignore[arg-type]
    assert antiabuse.client_ip(SimpleNamespace(client=None)) == "unknown"  # type: ignore[arg-type]
    state = SimpleNamespace()
    request = SimpleNamespace(app=SimpleNamespace(state=state))
    off = antiabuse.get_rate_limiter(request, make_settings(rate_limit_enabled=False))  # type: ignore[arg-type]
    assert type(off).__name__ == "NullRateLimiter"
    assert antiabuse.get_rate_limiter(request, make_settings()) is off  # type: ignore[arg-type]
