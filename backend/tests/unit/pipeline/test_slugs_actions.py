"""Slugs and the idempotent after-commit actions."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.pipeline import actions
from app.modules.pipeline.slugs import base_slug, slugify, unique_slug
from app.modules.pipeline.transitions import ACTION_ENSURE_DERIVATIVES, ACTION_FEED_INVALIDATE


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("Movienight: Film A", "movienight-film-a"),
        ("Fachschaftssitzung im Café", "fachschaftssitzung-im-cafe"),
        ("Größe, Übung & Äpfel", "groesse-uebung-aepfel"),
        ("!!!", "event"),
        ("x" * 100, "x" * 60),
    ],
)
def test_slugify(title: str, slug: str) -> None:
    assert slugify(title) == slug


def test_base_slug_uses_the_local_day() -> None:
    late = datetime(2026, 11, 5, 23, 30, tzinfo=UTC)
    assert base_slug("Kino", late, "Europe/Berlin") == "2026-11-06-kino"


class _Scalars:
    def __init__(self, items: list[str]) -> None:
        self.items = items

    def __iter__(self):  # noqa: ANN204
        return iter(self.items)


async def test_unique_slug_counts_up() -> None:
    class Session:
        def __init__(self, taken: list[str]) -> None:
            self.taken = taken

        async def scalars(self, _query: object) -> _Scalars:
            return _Scalars(self.taken)

    assert await unique_slug(Session([]), "2026-11-05-kino") == "2026-11-05-kino"  # type: ignore[arg-type]
    taken = ["2026-11-05-kino", "2026-11-05-kino-2", "2026-11-05-kino-extra"]
    assert await unique_slug(Session(taken), "2026-11-05-kino") == "2026-11-05-kino-3"  # type: ignore[arg-type]


class Pool:
    def __init__(self, fail: bool = False) -> None:
        self.keys: set[str] = set()
        self.incremented = 0
        self.jobs: list[tuple[str, str, str]] = []
        self.fail = fail

    async def set(self, key: str, value: str, nx: bool, ex: int) -> bool | None:
        if self.fail:
            raise ConnectionError("redis down")
        if key in self.keys:
            return None
        self.keys.add(key)
        return True

    async def incr(self, key: str) -> int:
        self.incremented += 1
        return self.incremented

    async def enqueue_job(self, name: str, arg: str, _job_id: str) -> None:
        self.jobs.append((name, arg, _job_id))


def committed(poster: bool = True, derived: bool = False) -> actions.Committed:
    return actions.Committed(uuid4(), 4, uuid4() if poster else None, derived)


def test_action_key_has_the_contract_shape() -> None:
    c = committed()
    assert actions.action_key(c, "x") == f"event:{c.event_id}:rev:4:x"


async def test_actions_run_once_per_revision() -> None:
    pool, c = Pool(), committed()
    for _ in range(2):
        await actions.run_actions(pool, (ACTION_FEED_INVALIDATE, ACTION_ENSURE_DERIVATIVES), c)
    assert pool.incremented == 1
    assert pool.jobs == [("derive_poster", str(c.poster_id), f"derive:{c.poster_id}")]


@pytest.mark.parametrize("c", [committed(poster=False), committed(derived=True)])
async def test_ensure_derivatives_skips_without_work(c: actions.Committed) -> None:
    pool = Pool()
    await actions.run_actions(pool, (ACTION_ENSURE_DERIVATIVES,), c)
    assert pool.jobs == []


async def test_a_failing_action_is_swallowed_and_without_pool_nothing_runs() -> None:
    await actions.run_actions(Pool(fail=True), (ACTION_FEED_INVALIDATE,), committed())
    await actions.run_actions(None, (ACTION_FEED_INVALIDATE,), committed())
