"""arq job `outbox_run`: send the pending Listmonk jobs, once a minute.

The Redis key `listmonk:open` is the circuit breaker; while it is set the job does nothing and the
outbox only grows. The domain logic lives in `app.modules.subscriptions.outbox`.
"""

from __future__ import annotations

from typing import Any

from app.modules.subscriptions.outbox import run_outbox
from worker.listmonk_deps import build_deps


async def outbox_run(ctx: dict[str, Any]) -> str:
    """Process the due outbox jobs; return the log line."""
    deps = build_deps(ctx)
    if deps is None:
        return "outbox_run: skipped (not configured)"
    stats = await run_outbox(deps.subs, deps.port, deps.email_key, breaker=ctx.get("redis"))
    return (
        f"outbox_run: done={stats.done} failed={stats.failed} dead={stats.dead} "
        f"breaker={stats.breaker_open}"
    )
