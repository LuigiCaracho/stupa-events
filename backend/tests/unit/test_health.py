"""Health endpoint, security headers, problem+json on unknown routes and `/auth/me`."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_ok_with_security_headers(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert response.headers["x-trace-id"]


def test_unknown_route_is_problem_json(client: TestClient) -> None:
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "not_found"


def test_me_requires_a_session(client: TestClient) -> None:
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthorized"


def test_login_is_404_without_oidc(client: TestClient) -> None:
    assert client.get("/api/auth/login", follow_redirects=False).status_code == 404
