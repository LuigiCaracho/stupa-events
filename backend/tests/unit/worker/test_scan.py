"""The scan worker: verdicts, quarantine, derive hand-off, retries."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from arq import Retry

import worker.scan as scan
from app.modules.files.scanner import ScannerError, ScanVerdict
from app.modules.files.storage import StorageError
from tests._support.factories import make_settings
from tests._support.memory_storage import MemoryStorage


class _Maker:
    def __init__(self, row: Any) -> None:
        self.row = row
        self.committed = False
        self.executed: list[Any] = []

    def __call__(self) -> _Maker:
        return self

    async def __aenter__(self) -> _Maker:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def get(self, model: Any, key: Any) -> Any:
        return self.row

    async def execute(self, statement: Any) -> None:
        self.executed.append(statement)

    async def commit(self) -> None:
        self.committed = True


class _Scanner:
    def __init__(self, verdict: ScanVerdict | Exception) -> None:
        self.verdict = verdict

    async def scan(self, data: bytes) -> ScanVerdict:
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return self.verdict


class _Pool:
    def __init__(self) -> None:
        self.jobs: list[tuple[Any, ...]] = []
        self.bumps = 0

    async def incr(self, key: str) -> int:
        self.bumps += 1
        return self.bumps

    async def enqueue_job(self, *args: Any, **kwargs: Any) -> None:
        self.jobs.append((*args, kwargs))


def _attachment(kind: str = "poster") -> Any:
    return SimpleNamespace(
        id=uuid.uuid4(),
        event_id=uuid.uuid4(),
        kind=kind,
        mime="image/png" if kind in ("poster", "social_post") else "application/pdf",
        storage_key="k",
        scan_status="pending",
        scan_result=None,
        supersedes_id=None,
    )


@pytest.fixture
def audit(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    async def fake(session: Any, **kwargs: Any) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(scan, "audit_record", fake)
    return calls


def _ctx(row: Any, verdict: ScanVerdict | Exception, **extra: Any) -> dict[str, Any]:
    storage = MemoryStorage()
    storage.blobs["k"] = b"data"
    return {
        "settings": make_settings(scan_max_tries=2, scan_retry_backoff_seconds=5),
        "scanner": _Scanner(verdict),
        "object_storage": storage,
        "files_sessionmaker": _Maker(row),
        **extra,
    }


async def test_clean_poster_is_stored_audited_and_handed_to_derive(audit: list[Any]) -> None:
    row, pool = _attachment(), _Pool()
    ctx = _ctx(row, ScanVerdict(clean=True), redis=pool)
    assert await scan.scan_attachment(ctx, str(row.id)) == "clean"
    assert row.scan_status == "clean"
    assert ctx["files_sessionmaker"].committed
    assert audit[0]["action"] == "attachment_scan"
    assert pool.jobs[0][:2] == ("derive_poster", str(row.id))
    assert pool.bumps == 0


async def test_other_kinds_are_not_derived(audit: list[Any]) -> None:
    row, pool = _attachment("quote"), _Pool()
    await scan.scan_attachment(_ctx(row, ScanVerdict(clean=True), redis=pool), str(row.id))
    assert pool.jobs == []


async def test_clean_without_pool_only_warns(audit: list[Any]) -> None:
    row = _attachment()
    assert await scan.scan_attachment(_ctx(row, ScanVerdict(clean=True)), str(row.id)) == "clean"


async def test_finding_removes_the_object_and_quarantines(audit: list[Any]) -> None:
    row = _attachment()
    ctx = _ctx(row, ScanVerdict(clean=False, signature="Eicar-Test"), redis=_Pool())
    assert await scan.scan_attachment(ctx, str(row.id)) == "infected"
    assert row.scan_status == "infected"
    assert row.scan_result == "Eicar-Test"
    assert row.storage_key is None
    assert "k" not in ctx["object_storage"].blobs
    assert audit[0]["action"] == "attachment_quarantine"
    assert [job[0] for job in ctx["redis"].jobs] == ["rebuild_public_cache"]


@pytest.mark.parametrize("kind,bumps", [("poster", 1), ("quote", 0)])
async def test_a_poster_verdict_bumps_the_feed_version(
    audit: list[Any], kind: str, bumps: int
) -> None:
    row, pool = _attachment(kind), _Pool()
    ctx = _ctx(row, ScanVerdict(clean=False, signature="Eicar-Test"), redis=pool)
    assert await scan.scan_attachment(ctx, str(row.id)) == "infected"
    assert pool.bumps == bumps


async def test_missing_row_and_missing_backends() -> None:
    assert (
        await scan.scan_attachment(_ctx(None, ScanVerdict(clean=True)), str(uuid.uuid4())) == "gone"
    )
    ctx = _ctx(_attachment(), ScanVerdict(clean=True))
    ctx["scanner"] = None
    assert await scan.scan_attachment(ctx, str(uuid.uuid4())) == "skipped"


@pytest.mark.parametrize("error", [ScannerError("down"), StorageError("down")])
async def test_transient_errors_retry_then_die(error: Exception, audit: list[Any]) -> None:
    row = _attachment()
    with pytest.raises(Retry):
        await scan.scan_attachment(_ctx(row, error, job_try=1), str(row.id))
    assert row.scan_status == "pending" and audit == []
    ctx = _ctx(row, error, job_try=2)
    assert await scan.scan_attachment(ctx, str(row.id)) == "dead"
    assert row.scan_status == "error" and ctx["files_sessionmaker"].committed
    assert audit[0]["data"]["status"] == "error"


async def test_a_clean_replacement_hides_its_predecessor(audit: list[Any]) -> None:
    row = _attachment("quote")
    row.supersedes_id = uuid.uuid4()
    ctx = _ctx(row, ScanVerdict(clean=True))
    await scan.scan_attachment(ctx, str(row.id))
    assert len(ctx["files_sessionmaker"].executed) == 1


async def test_an_infected_replacement_leaves_its_predecessor(audit: list[Any]) -> None:
    row = _attachment("quote")
    row.supersedes_id = uuid.uuid4()
    ctx = _ctx(row, ScanVerdict(clean=False, signature="x"))
    await scan.scan_attachment(ctx, str(row.id))
    assert ctx["files_sessionmaker"].executed == []


async def test_a_replaced_poster_is_not_retired_by_the_scan(audit: list[Any]) -> None:
    row = _attachment()
    row.supersedes_id = uuid.uuid4()
    ctx = _ctx(row, ScanVerdict(clean=True), redis=_Pool())
    await scan.scan_attachment(ctx, str(row.id))
    assert ctx["files_sessionmaker"].executed == []
