"""Create the Listmonk lists of the active categories (and `events-alle`) in the dev stack.

Run after the seed script has written the API token: `python -m scripts.listmonk_lists`. It uses
the same settings as the worker (`SUBS_DATABASE_URL`, `LISTMONK_*`). The call is idempotent.
"""

from __future__ import annotations

import asyncio

from app.modules.subscriptions.listmonk_sync import sync_category_lists
from worker.listmonk_deps import build_deps


async def main() -> None:
    """Sync the lists and print the counters."""
    ctx: dict[str, object] = {}
    deps = build_deps(ctx)
    if deps is None:
        raise SystemExit("SUBS_DATABASE_URL, PGCRYPTO_EMAIL_KEY and LISTMONK_* must be set")
    print(await sync_category_lists(deps.subs, deps.port))


if __name__ == "__main__":
    asyncio.run(main())
