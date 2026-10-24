"""arq job `build_digest_drafts`: weekly Listmonk campaign drafts, never sent by the job."""

from __future__ import annotations

from typing import Any

from app.modules.subscriptions.digest import build_drafts
from worker.listmonk_deps import build_deps


async def build_digest_drafts(ctx: dict[str, Any]) -> str:
    """Create the digest drafts of the week; return the log line."""
    deps = build_deps(ctx)
    if deps is None:
        return "build_digest_drafts: skipped (not configured)"
    counters = await build_drafts(deps.subs, deps.port, base_url=deps.settings.public_base_url)
    return f"build_digest_drafts: drafts={counters['drafts']} skipped={counters['skipped']}"
