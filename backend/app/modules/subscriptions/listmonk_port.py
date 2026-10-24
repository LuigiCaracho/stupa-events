"""Port to the mailing-list service (Listmonk): value classes, errors and the protocol.

The domain code talks to Listmonk only through `ListmonkPort`. The HTTP client implements it
and `tests/_support/fake_listmonk.py` implements it in memory. This module imports no HTTP
library. `ListmonkError.retryable` tells the outbox worker whether another try can help.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Literal, Protocol

SubscriberStatus = Literal["enabled", "blocklisted"]
ListStatus = Literal["unconfirmed", "confirmed", "unsubscribed"]


class ListmonkError(Exception):
    """A Listmonk call failed. The message carries the error class and status only."""

    def __init__(self, kind: str, *, status: int | None = None, retryable: bool = True) -> None:
        super().__init__(f"{kind}" if status is None else f"{kind} ({status})")
        self.kind = kind
        self.status = status
        self.retryable = retryable


@dataclass(frozen=True, slots=True)
class ListmonkSubscriber:
    """A subscriber as Listmonk holds it: status and the status per list id."""

    id: int
    email: str
    status: SubscriberStatus = "enabled"
    lists: dict[int, ListStatus] = field(default_factory=dict)
    attribs: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CampaignDraft:
    """A campaign to create as a draft; it never carries a send time."""

    name: str
    subject: str
    list_ids: tuple[int, ...]
    body: str


class ListmonkPort(Protocol):
    """Everything the platform needs from Listmonk."""

    async def ensure_list(self, key: str, name: str) -> int:
        """Return the id of the list called `name`; create it (private, single opt-in)."""
        ...

    async def find_subscriber(self, email: str) -> ListmonkSubscriber | None:
        """Return the subscriber with this address or None."""
        ...

    async def upsert_subscriber(
        self, email: str, list_ids: set[int], attribs: dict[str, object]
    ) -> ListmonkSubscriber:
        """Create the subscriber or move it to exactly `list_ids` (confirmed), merge `attribs`."""
        ...

    async def blocklist(self, subscriber_id: int) -> None:
        """Blocklist the subscriber."""
        ...

    async def resubscribe(self, existing: ListmonkSubscriber, list_ids: set[int]) -> None:
        """Lift a blocklist and confirm `list_ids` again, after a new double opt-in of ours."""
        ...

    async def archive_list(self, list_id: int) -> None:
        """Archive the list; Listmonk keeps it, nothing is deleted."""
        ...

    async def delete_subscriber(self, subscriber_id: int) -> None:
        """Delete the subscriber; a missing one is not an error."""
        ...

    def list_states(self, list_ids: set[int]) -> AsyncIterator[ListmonkSubscriber]:
        """Stream every subscriber that sits on one of the lists, each once."""
        ...

    async def create_campaign(self, draft: CampaignDraft) -> int:
        """Create the campaign in status draft and return its id."""
        ...

    async def find_campaign(self, name: str) -> int | None:
        """Return the id of the campaign with exactly this name or None."""
        ...

    async def campaign_status(self, campaign_id: int) -> str:
        """Return the Listmonk status of the campaign (draft, running, finished, ...)."""
        ...

    async def start_campaign(self, campaign_id: int) -> None:
        """Release the campaign for sending."""
        ...

    async def subscriber_count(self, list_id: int) -> int:
        """Return the number of subscribers on the list."""
        ...
