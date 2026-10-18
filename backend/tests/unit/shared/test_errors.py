"""Problem+JSON: core members, extension members and their precedence."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middleware import RequestContextMiddleware
from app.shared.errors import AppError, ConflictError, register_exception_handlers


class _Refused(AppError):
    status = 422


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)

    @app.get("/refused")
    def refused() -> None:
        raise _Refused(
            "blocked",
            code="image_required",
            extensions={"reasons": [{"code": "image_required"}], "code": "overridden"},
        )

    @app.get("/conflict")
    def conflict() -> None:
        raise ConflictError("stale", code="field_locked")

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret")

    return TestClient(app, raise_server_exceptions=False)


def test_extensions_are_merged_but_never_replace_core_members() -> None:
    response = _client().get("/refused")
    body = response.json()
    assert response.status_code == 422
    assert body["code"] == "image_required"
    assert body["type"] == "app://error/image_required"
    assert body["reasons"] == [{"code": "image_required"}]
    assert body["traceId"]


def test_plain_error_has_no_extra_members() -> None:
    body = _client().get("/conflict").json()
    assert body["code"] == "field_locked"
    assert set(body) == {"type", "title", "status", "code", "detail", "traceId"}


def test_unhandled_error_leaks_nothing() -> None:
    response = _client().get("/boom")
    assert response.status_code == 500
    assert "secret" not in response.text
