"""Clients of the B3 acceptance: public subscription API, Mailpit and the Listmonk admin API.

`sign_up` solves a fresh ALTCHA challenge for every POST, the way the SPA does. Mails come from
Mailpit (`127.0.0.1:8025`), which receives both the API mails (through the worker) and the
Listmonk campaigns. The Listmonk client uses the API user of the dev env (`LISTMONK_API_*`).
Only for the local stack.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.shared.altcha import Challenge, solve_challenge
from scripts.acceptance_common import API, check

MAILPIT = "http://127.0.0.1:8025"
LISTMONK = os.environ.get("LISTMONK_URL", "http://127.0.0.1:9002")
LINK = re.compile(r"https?://[^\s\"<>]+/(bestaetigen|abo)/([A-Za-z0-9_-]{43})")


def anonymous() -> httpx.Client:
    """Return a client without cookies against the API."""
    return httpx.Client(base_url=API, timeout=30.0)


def altcha(client: httpx.Client) -> str:
    """Fetch and solve one ALTCHA challenge."""
    response = client.get("/api/public/altcha/challenge")
    if response.status_code != 200:
        check(False, f"ALTCHA challenge -> 200 (got {response.status_code})")
    return solve_challenge(Challenge(**response.json()))


def questionnaire(client: httpx.Client) -> dict[str, Any]:
    """Return the questionnaire."""
    return client.get("/api/public/getstarted/questions").json()


def body(
    client: httpx.Client,
    *,
    interests: list[str],
    meetings: bool = False,
    email: str | None = None,
    faculty: str | None = None,
) -> dict[str, Any]:
    """Build a sign-up body with the current questionnaire and consent versions."""
    q = questionnaire(client)
    return {
        "questionnaireVersion": q["version"],
        "answers": {
            "interests": interests,
            "meetings": meetings,
            "faculty": faculty,
            "mail": email is not None,
        },
        "email": email,
        "consent": {"version": q["consent"]["version"], "accepted": True} if email else None,
        "altcha": altcha(client),
    }


def sign_up(client: httpx.Client, **kw: Any) -> httpx.Response:
    """POST one sign-up."""
    return client.post("/api/public/subscriptions", json=body(client, **kw))


def manage_link(client: httpx.Client, email: str) -> httpx.Response:
    """Ask for a management link."""
    payload = {"email": email, "altcha": altcha(client)}
    return client.post("/api/public/subscriptions/manage-link", json=payload)


def me(client: httpx.Client, token: str, method: str = "GET", **kw: Any) -> httpx.Response:
    """Call a management route with the token in the header."""
    headers = {"X-Subscription-Token": token}
    return client.request(method, "/api/public/subscriptions/me", headers=headers, **kw)


@dataclass(frozen=True, slots=True)
class Mail:
    """A mail in Mailpit: id, subject, text and the token link."""

    id: str
    subject: str
    text: str
    kind: str | None
    token: str | None


def _mailpit(client: httpx.Client, path: str, **params: Any) -> Any:
    return client.get(f"{MAILPIT}{path}", params=params, timeout=10.0).json()


def mails(to: str) -> list[Mail]:
    """Return the mails to `to`, newest first."""
    with httpx.Client() as client:
        found = _mailpit(client, "/api/v1/search", query=f'to:"{to}"')["messages"]
        out = []
        for item in found:
            full = _mailpit(client, f"/api/v1/message/{item['ID']}")
            link = LINK.search(full.get("Text", "") + full.get("HTML", ""))
            out.append(
                Mail(
                    item["ID"],
                    item["Subject"],
                    full.get("Text", ""),
                    link.group(1) if link else None,
                    link.group(2) if link else None,
                )
            )
        return out


def wait_mail(to: str, subject_part: str, *, known: int = 0, timeout: float = 60) -> Mail:
    """Wait until more than `known` mails with `subject_part` reached `to`; return the newest."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        hits = [m for m in mails(to) if subject_part in m.subject]
        if len(hits) > known:
            return hits[0]
        time.sleep(1)
    check(False, f"mail '{subject_part}' reached {to.split('@')[1]}")
    raise AssertionError


def count_mails(to: str, subject_part: str) -> int:
    """Count the mails with `subject_part` to `to`."""
    return sum(subject_part in m.subject for m in mails(to))


def mail_headers(mail_id: str) -> dict[str, list[str]]:
    """Return the headers of one mail."""
    with httpx.Client() as client:
        return _mailpit(client, f"/api/v1/message/{mail_id}/headers")


class Listmonk:
    """The Listmonk admin API with the API user of the dev env."""

    def __init__(self) -> None:
        user, token = os.environ["LISTMONK_API_USER"], os.environ["LISTMONK_API_TOKEN"]
        self.http = httpx.Client(
            base_url=LISTMONK, headers={"Authorization": f"token {user}:{token}"}, timeout=15.0
        )

    def subscriber(self, email: str) -> dict[str, Any] | None:
        """Return the subscriber with exactly this address or None."""
        rows = self.http.get("/api/subscribers", params={"search": email, "per_page": 100})
        results = rows.json()["data"]["results"] or []
        return next((r for r in results if r["email"].lower() == email.lower()), None)

    def list_names(self, subscriber: dict[str, Any]) -> dict[str, str]:
        """Return list name to subscription status of a subscriber."""
        return {item["name"]: item["subscription_status"] for item in subscriber["lists"]}

    def campaigns(self, name_part: str) -> list[dict[str, Any]]:
        """Return the campaigns whose name contains `name_part`."""
        data = self.http.get("/api/campaigns", params={"query": name_part, "per_page": "all"})
        return data.json()["data"]["results"] or []

    def settings(self) -> dict[str, Any]:
        """Return the Listmonk settings."""
        return self.http.get("/api/settings").json()["data"]

    def healthy(self) -> bool:
        """Report whether Listmonk answers."""
        try:
            return self.http.get("/health").status_code == 200
        except httpx.HTTPError:
            return False


def json_line(value: Any) -> str:
    """Return compact JSON for the protocol."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)
