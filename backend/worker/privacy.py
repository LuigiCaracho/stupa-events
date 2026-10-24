"""arq job `purge_expired`: the retention functions of PLAN 8.9, once a day."""

from __future__ import annotations

from typing import Any

from app.modules.subscriptions.privacy import purge_expired as purge
from worker.listmonk_deps import build_deps


async def purge_expired(ctx: dict[str, Any]) -> str:
    """Purge pending, unsubscribed, expired profile and finished outbox rows; return counts."""
    deps = build_deps(ctx, need_port=False)
    if deps is None:
        return "purge_expired: skipped (not configured)"
    counts = await purge(deps.subs, deps.app)
    return "purge_expired: " + " ".join(f"{k}={v}" for k, v in counts.items())
