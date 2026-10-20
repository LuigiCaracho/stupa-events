"""Worker functions of the dossier module, registered by `worker.main`."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from app.modules.dossier.derive import derive_poster
from app.modules.dossier.previews import build_preview
from app.modules.dossier.promote import promote_poster

WORKER_FUNCTIONS: tuple[Callable[..., Coroutine[Any, Any, Any]], ...] = (
    derive_poster,
    build_preview,
    promote_poster,
)
