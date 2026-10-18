"""Auth unit fixtures: the membership sync is a recording stub (its own tests cover it)."""

from __future__ import annotations

from typing import Any

import pytest

from app.modules.auth import service


@pytest.fixture(autouse=True)
def sync_calls(monkeypatch: pytest.MonkeyPatch) -> list[Any]:
    """Replace `sync_principal_memberships` in the auth service; return the rows it saw."""
    seen: list[Any] = []

    async def stub(db: Any, row: Any) -> bool:
        seen.append(row)
        return False

    monkeypatch.setattr(service, "sync_principal_memberships", stub)
    return seen
