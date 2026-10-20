"""The dossier module registers `derive_poster`, `build_preview` and `promote_poster`."""

from __future__ import annotations

from app.modules.dossier import derive
from app.modules.dossier.worker_jobs import WORKER_FUNCTIONS
from tests._support.factories import make_settings
from worker.scan import DERIVE_TASK_NAME


def test_the_registered_function_has_the_enqueued_name() -> None:
    names = [fn.__name__ for fn in WORKER_FUNCTIONS]
    assert names == ["derive_poster", "build_preview", "promote_poster"]
    assert names[0] == DERIVE_TASK_NAME


def test_the_public_storage_is_built_once_per_worker() -> None:
    ctx = {
        "settings": make_settings(
            minio_endpoint="minio:9000", minio_access_key="a", minio_secret_key="b"
        )
    }
    first = derive._public_storage(ctx)
    assert first is not None and first.bucket == "events-public"  # type: ignore[attr-defined]
    assert derive._public_storage(ctx) is first


async def test_without_storage_the_job_is_skipped() -> None:
    assert (
        await derive.derive_poster(
            {"settings": make_settings()}, "00000000-0000-0000-0000-000000000000"
        )
        == "skipped"
    )


def test_derivative_keys() -> None:
    assert derive.derivative_key("abc-card_1200") == "derivatives/abc-card_1200.webp"
