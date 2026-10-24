"""The rate-limit key is the forwarded client only when the direct peer is a trusted proxy.

uvicorn's `ProxyHeadersMiddleware` (the `--proxy-headers` of the image CMD) decides; `client_ip`
parses no header itself, so a forged `X-Forwarded-For` from anywhere else must not move the key.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.shared.antiabuse import client_ip

TRUSTED = "172.29.10.10"
FORGED = "6.6.6.6"


def _app() -> FastAPI:
    app = FastAPI()

    @app.get("/who")
    async def who(request: Request) -> dict[str, str]:
        return {"key": client_ip(request)}

    return app


def _key(peer: str, forwarded: str) -> str:
    wrapped = ProxyHeadersMiddleware(_app(), trusted_hosts=TRUSTED)
    with TestClient(wrapped, client=(peer, 50000)) as http:
        return http.get("/who", headers={"X-Forwarded-For": forwarded}).json()["key"]


def test_a_trusted_proxy_hands_over_the_visitor() -> None:
    assert _key(TRUSTED, "203.0.113.7") == "203.0.113.7"


def test_the_key_ignores_a_forged_header_from_an_untrusted_peer() -> None:
    assert _key("172.29.10.99", FORGED) == "172.29.10.99"


def test_the_appended_hop_wins_over_a_forged_first_entry() -> None:
    assert _key(TRUSTED, f"{FORGED}, 203.0.113.7") == "203.0.113.7"
