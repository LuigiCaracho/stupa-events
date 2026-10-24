"""arq job `reconcile_listmonk`: daily comparison of our subscribers with Listmonk."""

from __future__ import annotations

from typing import Any

from app.modules.subscriptions.reconcile import reconcile
from worker.listmonk_deps import build_deps


async def reconcile_listmonk(ctx: dict[str, Any]) -> str:
    """Run the reconcile; return the counters as a log line."""
    deps = build_deps(ctx)
    if deps is None:
        return "reconcile_listmonk: skipped (not configured)"
    report = await reconcile(deps.subs, deps.port, deps.email_key)
    return (
        f"reconcile_listmonk: seen={report.seen} unsubscribed={report.unsubscribed} "
        f"dropped={report.categories_dropped} foreign={report.foreign_on_lists} "
        f"requeued={report.requeued} released={report.released_digests}"
    )
