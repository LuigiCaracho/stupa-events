"""Outbox retry timing."""

from __future__ import annotations

import pytest

from app.modules.subscriptions.outbox import backoff_seconds


@pytest.mark.parametrize(
    ("attempts", "wait"), [(1, 60), (2, 120), (3, 240), (6, 1920), (7, 3600), (10, 3600)]
)
def test_backoff_doubles_and_caps_at_one_hour(attempts: int, wait: int) -> None:
    assert backoff_seconds(attempts) == wait
