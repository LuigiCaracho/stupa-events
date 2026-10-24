"""In-memory `ListmonkPort` with fault injection, for the outbox, reconcile and digest tests.

It follows the observed Listmonk v5.1 behaviour that the contract test pins down: a blocklisted
subscriber is not re-enabled by an upsert, a list the person left stays `unsubscribed`, a list
that is not wanted any more is removed, a campaign starts as `draft`, deleting a missing
subscriber succeeds. `down` makes every call fail like an unreachable server, `fail_next` fails
the next calls with a given error; `calls` records the method names.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import replace

from app.modules.subscriptions.listmonk_port import (
    CampaignDraft,
    ListmonkError,
    ListmonkSubscriber,
)


class FakeListmonk:
    """A scriptable Listmonk."""

    def __init__(self) -> None:
        self.lists: dict[int, str] = {}
        self.archived: set[int] = set()
        self.subscribers: dict[int, ListmonkSubscriber] = {}
        self.campaigns: dict[int, dict[str, object]] = {}
        self.calls: list[str] = []
        self.down = False
        self._failures: list[ListmonkError] = []
        self._next_id = 1

    def fail_next(self, count: int, error: ListmonkError | None = None) -> None:
        """Fail the next `count` calls with `error` (default: a retryable 503)."""
        self._failures = [error or ListmonkError("http_error", status=503)] * count

    def _enter(self, name: str) -> None:
        self.calls.append(name)
        if self.down:
            raise ListmonkError("ConnectError")
        if self._failures:
            raise self._failures.pop(0)

    def _id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    def by_email(self, email: str) -> ListmonkSubscriber | None:
        """Look a subscriber up without recording a call."""
        return next((s for s in self.subscribers.values() if s.email == email), None)

    def user_unsubscribes(self, email: str, list_id: int) -> None:
        """Simulate the unsubscribe link of a mail for one list."""
        found = self.by_email(email)
        assert found is not None
        self.subscribers[found.id] = replace(found, lists={**found.lists, list_id: "unsubscribed"})

    def user_blocklists(self, email: str) -> None:
        """Simulate a blocklisting inside Listmonk."""
        found = self.by_email(email)
        assert found is not None
        lists = dict.fromkeys(found.lists, "unsubscribed")
        self.subscribers[found.id] = replace(found, status="blocklisted", lists=lists)

    def add_foreign(self, email: str, list_id: int) -> ListmonkSubscriber:
        """Put a subscriber onto a list that our database does not know."""
        sub = ListmonkSubscriber(self._id(), email, "enabled", {list_id: "confirmed"})
        self.subscribers[sub.id] = sub
        return sub

    async def ensure_list(self, key: str, name: str) -> int:
        self._enter("ensure_list")
        found = next((i for i, n in self.lists.items() if n == name), None)
        if found is not None:
            return found
        new = self._id()
        self.lists[new] = name
        return new

    async def find_subscriber(self, email: str) -> ListmonkSubscriber | None:
        self._enter("find_subscriber")
        return self.by_email(email)

    async def upsert_subscriber(
        self, email: str, list_ids: set[int], attribs: dict[str, object]
    ) -> ListmonkSubscriber:
        self._enter("upsert_subscriber")
        existing = self.by_email(email)
        if existing is None:
            created = ListmonkSubscriber(
                self._id(), email, "enabled", dict.fromkeys(list_ids, "confirmed"), dict(attribs)
            )
            self.subscribers[created.id] = created
            return created
        if existing.status == "blocklisted":
            return existing
        lists = {i: s for i, s in existing.lists.items() if i in list_ids or s == "unsubscribed"}
        for list_id in list_ids - lists.keys():
            lists[list_id] = "confirmed"
        updated = replace(existing, lists=lists, attribs={**existing.attribs, **attribs})
        self.subscribers[updated.id] = updated
        return updated

    async def blocklist(self, subscriber_id: int) -> None:
        self._enter("blocklist")
        found = self.subscribers.get(subscriber_id)
        if found is not None:
            self.user_blocklists(found.email)

    async def archive_list(self, list_id: int) -> None:
        self._enter("archive_list")
        self.archived.add(list_id)

    async def delete_subscriber(self, subscriber_id: int) -> None:
        self._enter("delete_subscriber")
        self.subscribers.pop(subscriber_id, None)

    async def list_states(self, list_ids: set[int]) -> AsyncIterator[ListmonkSubscriber]:
        self._enter("list_states")
        for sub in list(self.subscribers.values()):
            if sub.lists.keys() & list_ids:
                yield sub

    async def create_campaign(self, draft: CampaignDraft) -> int:
        self._enter("create_campaign")
        new = self._id()
        self.campaigns[new] = {"draft": draft, "status": "draft"}
        return new

    async def find_campaign(self, name: str) -> int | None:
        self._enter("find_campaign")
        return next((i for i, c in self.campaigns.items() if c["draft"].name == name), None)  # type: ignore[attr-defined]

    async def campaign_status(self, campaign_id: int) -> str:
        self._enter("campaign_status")
        return str(self.campaigns[campaign_id]["status"])

    async def start_campaign(self, campaign_id: int) -> None:
        self._enter("start_campaign")
        self.campaigns[campaign_id]["status"] = "running"

    async def subscriber_count(self, list_id: int) -> int:
        self._enter("subscriber_count")
        return sum(1 for s in self.subscribers.values() if s.lists.get(list_id) == "confirmed")
