"""HTTP client for the Listmonk admin API; it implements `ListmonkPort`.

The base URL is operator configuration, never user input: the scheme must be https (http only
for loopback in development) and the host must sit in `LISTMONK_ALLOWED_HOSTS`. The IP check of
the SSRF guard is off for exactly that allowlist, because Listmonk lives in the Docker network
or on loopback. Redirects are never followed. Errors carry the class and the status, never the
response body or a request payload, so no address reaches a log.

Listmonk v5.1 has no `PATCH /api/subscribers/{id}`. Attributes change through `PUT
/api/subscribers/{id}` with the full list of current lists, which keeps their statuses
(an `unsubscribed` list stays `unsubscribed`); removals go through `PUT /api/subscribers/lists`.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.modules.subscriptions.listmonk_port import (
    CampaignDraft,
    ListmonkError,
    ListmonkSubscriber,
)
from app.shared.ssrf import SsrfError, assert_allowed_url

SUBSCRIBER_NAME = "STUPA Events Abo"
PAGE_SIZE = 500
_UNSAFE = re.compile(r"[\x00-\x1f\x7f\\]")
_TIMEOUT = httpx.Timeout(15.0, connect=3.0, read=10.0)


def checked_base_url(url: str, allowed_hosts: list[str], *, development: bool) -> str:
    """Validate the configured Listmonk URL and return it without a trailing slash.

    Raises:
        ListmonkError: Scheme, host or allowlist do not fit.
    """
    host = urlsplit(url).hostname or ""
    loopback = host == "localhost" or _is_loopback(host)
    scheme = urlsplit(url).scheme.lower()
    if scheme != "https" and not (development and loopback and scheme == "http"):
        raise ListmonkError("insecure_scheme", retryable=False)
    try:
        assert_allowed_url(url, allowlist=allowed_hosts or ["-"], allow_private=True)
    except SsrfError as exc:
        raise ListmonkError("host_not_allowed", retryable=False) from exc
    return url.rstrip("/")


def _is_loopback(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _subscriber(row: dict[str, Any]) -> ListmonkSubscriber:
    return ListmonkSubscriber(
        id=int(row["id"]),
        email=str(row["email"]),
        status="blocklisted" if row.get("status") == "blocklisted" else "enabled",
        lists={int(item["id"]): item["subscription_status"] for item in row.get("lists") or []},
        attribs=dict(row.get("attribs") or {}),
    )


class ListmonkClient:
    """`ListmonkPort` on top of httpx."""

    def __init__(
        self,
        base_url: str,
        user: str,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"token {user}:{token}"},
            timeout=_TIMEOUT,
            follow_redirects=False,
            transport=transport,
        )

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._http.aclose()

    async def _call(
        self, method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None
    ) -> Any:
        try:
            response = await self._http.request(method, path, json=json, params=params)
        except httpx.HTTPError as exc:
            raise ListmonkError(type(exc).__name__) from None
        status = response.status_code
        if status >= 400:
            raise ListmonkError(
                "http_error", status=status, retryable=status in (408, 429) or status >= 500
            )
        try:
            return response.json().get("data")
        except ValueError:
            raise ListmonkError("bad_response", status=status) from None

    async def _results(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        data = await self._call("GET", path, params=params)
        return list((data or {}).get("results") or [])

    async def ensure_list(self, key: str, name: str) -> int:
        """Return the id of the list `name`; create it as private list with single opt-in."""
        found = [r for r in await self._results("/api/lists", {"query": name, "per_page": "all"})]
        for row in found:
            if row["name"] == name:
                return int(row["id"])
        body = {"name": name, "type": "private", "optin": "single", "tags": ["events"]}
        return int((await self._call("POST", "/api/lists", json=body))["id"])

    async def find_subscriber(self, email: str) -> ListmonkSubscriber | None:
        """Return the subscriber with this address or None."""
        if _UNSAFE.search(email):
            raise ListmonkError("unsafe_address", retryable=False)
        query = "subscribers.email='" + email.replace("'", "''") + "'"
        rows = await self._results("/api/subscribers", {"query": query, "per_page": 1})
        return _subscriber(rows[0]) if rows else None

    async def upsert_subscriber(
        self, email: str, list_ids: set[int], attribs: dict[str, object]
    ) -> ListmonkSubscriber:
        """Create the subscriber or move it to exactly `list_ids`; never re-enables a block."""
        existing = await self.find_subscriber(email)
        if existing is None:
            body = {
                "email": email,
                "name": SUBSCRIBER_NAME,
                "status": "enabled",
                "lists": sorted(list_ids),
                "attribs": attribs,
                "preconfirm_subscriptions": True,
            }
            return _subscriber(await self._call("POST", "/api/subscribers", json=body))
        if existing.status == "blocklisted":
            return existing
        merged = {**existing.attribs, **attribs}
        if list_ids - existing.lists.keys() or merged != existing.attribs:
            body = {
                "email": email,
                "name": SUBSCRIBER_NAME,
                "status": "enabled",
                "lists": sorted(existing.lists.keys() | list_ids),
                "attribs": merged,
                "preconfirm_subscriptions": True,
            }
            await self._call("PUT", f"/api/subscribers/{existing.id}", json=body)
        stale = [
            i for i, st in existing.lists.items() if i not in list_ids and st != "unsubscribed"
        ]
        if stale:
            body = {"ids": [existing.id], "action": "remove", "target_list_ids": sorted(stale)}
            await self._call("PUT", "/api/subscribers/lists", json=body)
        refreshed = await self.find_subscriber(email)
        return refreshed or existing

    async def blocklist(self, subscriber_id: int) -> None:
        """Blocklist the subscriber; Listmonk then unsubscribes it from every list."""
        await self._call("PUT", f"/api/subscribers/{int(subscriber_id)}/blocklist")

    async def archive_list(self, list_id: int) -> None:
        """Archive the list."""
        row = await self._call("GET", f"/api/lists/{int(list_id)}")
        body = {
            "name": row["name"],
            "type": row["type"],
            "optin": row["optin"],
            "status": "archived",
        }
        await self._call("PUT", f"/api/lists/{int(list_id)}", json=body)

    async def delete_subscriber(self, subscriber_id: int) -> None:
        """Delete the subscriber; Listmonk answers success for a missing one."""
        await self._call("DELETE", f"/api/subscribers/{int(subscriber_id)}")

    async def list_states(self, list_ids: set[int]) -> AsyncIterator[ListmonkSubscriber]:
        """Stream every subscriber of the lists once, page by page."""
        seen: set[int] = set()
        for list_id in sorted(list_ids):
            page = 1
            while True:
                params = {"list_id": int(list_id), "per_page": PAGE_SIZE, "page": page}
                rows = await self._results("/api/subscribers", params)
                for row in rows:
                    if int(row["id"]) not in seen:
                        seen.add(int(row["id"]))
                        yield _subscriber(row)
                if len(rows) < PAGE_SIZE:
                    break
                page += 1

    async def create_campaign(self, draft: CampaignDraft) -> int:
        """Create a campaign; Listmonk stores it as draft."""
        body = {
            "name": draft.name,
            "subject": draft.subject,
            "lists": list(draft.list_ids),
            "type": "regular",
            "content_type": "html",
            "body": draft.body,
            "messenger": "email",
        }
        return int((await self._call("POST", "/api/campaigns", json=body))["id"])

    async def find_campaign(self, name: str) -> int | None:
        """Return the id of the campaign with exactly this name."""
        rows = await self._results("/api/campaigns", {"query": name, "per_page": "all"})
        return next((int(r["id"]) for r in rows if r["name"] == name), None)

    async def campaign_status(self, campaign_id: int) -> str:
        """Return the Listmonk status of the campaign."""
        return str((await self._call("GET", f"/api/campaigns/{int(campaign_id)}"))["status"])

    async def start_campaign(self, campaign_id: int) -> None:
        """Set the campaign to running."""
        body = {"status": "running"}
        await self._call("PUT", f"/api/campaigns/{int(campaign_id)}/status", json=body)

    async def subscriber_count(self, list_id: int) -> int:
        """Count the confirmed subscriptions of the list (live, not the cached list counter)."""
        params = {"list_id": int(list_id), "subscription_status": "confirmed", "per_page": 1}
        data = await self._call("GET", "/api/subscribers", params=params)
        return int(data["total"])
