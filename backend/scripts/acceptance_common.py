"""Shared helpers of the acceptance scripts: protocol lines and the real OIDC login.

The login goes through the login form of the dev Keycloak (code flow with PKCE), so roles
come from the IdP groups. Only for the local stack: the scripts refuse any API host other
than localhost. The callback URL of the dev env points at `ng serve` (:4200); the helper
replays it against the API itself, which works because cookies are not port-bound.
"""

from __future__ import annotations

import html
import os
import re
import sys
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

API = os.environ.get("M1_API", "http://localhost:8000")
PREFIX = ["m1"]
PASSWORD = "password"
_FORM_ACTION = re.compile(r'<form[^>]*id="kc-form-login"[^>]*action="([^"]+)"')


def step(message: str) -> None:
    """Print one protocol line."""
    print(f"[{PREFIX[0]}] {message}", flush=True)


def check(condition: bool, message: str) -> None:
    """Stop the run with `message` unless `condition` holds."""
    if not condition:
        print(f"[{PREFIX[0]}] FAIL: {message}", flush=True)
        sys.exit(1)
    step(f"ok   {message}")


def to_api(url: str) -> str:
    """Point a URL of the dev frontend (any localhost port) at the API."""
    parts, api = urlsplit(url), urlsplit(API)
    return urlunsplit((api.scheme, api.netloc, parts.path, parts.query, ""))


def login(username: str) -> httpx.Client:
    """Log in `username` through Keycloak; return a client with session and CSRF header."""
    client = httpx.Client(base_url=API, timeout=20.0)
    to_idp = client.get("/api/auth/login", follow_redirects=False)
    check(to_idp.status_code in {302, 303, 307}, f"{username}: /api/auth/login redirects")
    idp_url = to_idp.headers["location"]
    check(urlsplit(idp_url).hostname == "localhost", "IdP is the local Keycloak")
    form = client.get(idp_url, follow_redirects=True)
    # Keycloak marks its cookies Secure even on http; browsers send them to localhost anyway.
    for cookie in client.cookies.jar:
        cookie.secure = False
    action = _FORM_ACTION.search(form.text)
    check(action is not None, f"{username}: Keycloak shows the login form")
    assert action is not None
    back = client.post(
        html.unescape(action.group(1)),
        data={"username": username, "password": PASSWORD, "credentialId": ""},
        follow_redirects=False,
    )
    callback = back.headers.get("location", "")
    check("/api/auth/callback" in callback, f"{username}: Keycloak returns a code")
    done = client.get(to_api(callback), follow_redirects=False)
    check(done.status_code in {302, 303, 307}, f"{username}: callback opens the session")
    client.get("/api/auth/me")
    token = client.cookies.get("XSRF-TOKEN")
    if token:
        client.headers["X-XSRF-TOKEN"] = token
    return client


def confirm_location(client: httpx.Client, event_id: str) -> None:
    """Confirm a free venue text as the logged-in approver, as T04 requires since M5.

    A caller without `event.approve` gets 403 and nothing changes, which is what the
    scripts that test the refusal of T04 for organizers want.
    """
    event = client.get(f"/api/events/{event_id}").json()
    if (
        event.get("venueId") is None
        and event.get("venueText")
        and not event.get("locationConfirmedAt")
    ):
        client.post(
            f"/api/events/{event_id}/actions/confirm-location", json={"precision": "building"}
        )


def feed_pages() -> list[httpx.Response]:
    """Read the whole public feed page by page (the dev database outgrows one page)."""
    pages: list[httpx.Response] = []
    cursor = None
    while True:
        params = {"limit": 500, **({"cursor": cursor} if cursor else {})}
        pages.append(httpx.get(f"{API}/api/public/feed/events", params=params, timeout=20.0))
        cursor = pages[-1].json().get("nextCursor")
        if not cursor:
            return pages


def feed_items() -> list[dict[str, Any]]:
    """Return every item of the public feed."""
    return [item for page in feed_pages() for item in page.json()["items"]]


def expect(response: httpx.Response, status: int, what: str) -> Any:
    """Check the status of `response`; return its JSON body."""
    body = response.json() if response.content else {}
    detail = "" if response.status_code == status else f" (got {response.status_code}: {body})"
    check(response.status_code == status, f"{what} -> {status}{detail}")
    return body
