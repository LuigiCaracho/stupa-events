"""CSRF double submit, the default write limit and the trace id."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import (
    CsrfMiddleware,
    DefaultWriteRateLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.modules.auth import sessions
from app.shared.errors import register_exception_handlers
from app.shared.ratelimit import InMemoryRateLimiter
from tests._support.factories import make_settings


def _client(limiter: InMemoryRateLimiter | None = None, **settings: object) -> TestClient:
    cfg = make_settings(**settings)
    app = FastAPI()
    app.add_middleware(DefaultWriteRateLimitMiddleware, settings=cfg, limiter=limiter)
    app.add_middleware(CsrfMiddleware, settings=cfg)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    register_exception_handlers(app)

    @app.post("/api/x")
    def write() -> str:
        return "ok"

    @app.get("/api/public/x")
    def public() -> str:
        return "ok"

    return TestClient(app)


def test_cookie_authenticated_write_needs_the_csrf_header() -> None:
    client = _client()
    client.cookies.set("ev_session", "anything")
    response = client.post("/api/x")
    assert response.status_code == 403 and response.json()["code"] == "csrf_failed"
    client.cookies.set("XSRF-TOKEN", "t1")
    assert client.post("/api/x", headers={"X-XSRF-TOKEN": "t2"}).status_code == 403
    assert client.post("/api/x", headers={"X-XSRF-TOKEN": "t1"}).status_code == 200


def test_requests_without_session_cookie_or_with_bearer_skip_csrf_and_get_the_cookie() -> None:
    client = _client()
    response = client.post("/api/x")
    assert response.status_code == 200
    assert "XSRF-TOKEN" in response.cookies
    client.cookies.set("ev_session", "anything")
    assert client.post("/api/x", headers={"Authorization": "Bearer t"}).status_code == 200


def test_csrf_can_be_switched_off() -> None:
    client = _client(csrf_enabled=False)
    client.cookies.set("ev_session", "anything")
    assert client.post("/api/x").status_code == 200
    assert "XSRF-TOKEN" not in client.get("/api/public/x").cookies


def test_write_limit_keys_on_the_signed_session_else_the_ip() -> None:
    limiter = InMemoryRateLimiter()
    client = _client(limiter, csrf_enabled=False, rl_default_write_per_hour=2)
    assert [client.post("/api/x").status_code for _ in range(3)] == [200, 200, 429]
    blocked = client.post("/api/x")
    assert blocked.json()["code"] == "rate_limited" and blocked.headers["retry-after"]
    session = _client(limiter, csrf_enabled=False, rl_default_write_per_hour=2)
    session.cookies.set("ev_session", sessions.sign_principal_sid("test-session-secret", "sid-9"))
    assert [session.post("/api/x").status_code for _ in range(3)] == [200, 200, 200]
    forged = _client(limiter, csrf_enabled=False, rl_default_write_per_hour=2)
    forged.cookies.set("ev_session", "forged")
    assert forged.post("/api/x").status_code == 429


def test_reads_are_not_limited_and_public_answers_carry_noindex() -> None:
    client = _client(InMemoryRateLimiter(), rl_default_write_per_hour=1)
    assert all(client.get("/api/public/x").status_code == 200 for _ in range(5))
    assert client.get("/api/public/x").headers["x-robots-tag"] == "noindex"
    assert "x-robots-tag" not in client.get("/api/missing").headers
