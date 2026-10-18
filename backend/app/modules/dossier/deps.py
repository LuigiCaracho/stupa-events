"""Dependencies of the dossier and public routers: object storage and scan queue."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Request

from app.modules.files.queue import ScanQueue, scan_queue_from_pool
from app.modules.files.storage import ObjectStorage, build_object_storage
from app.settings import get_settings


def attachment_storage(request: Request) -> ObjectStorage | None:
    """Return the private attachment storage opened at startup (`None` when off)."""
    return getattr(request.app.state, "object_storage", None)


@lru_cache
def _public_storage() -> ObjectStorage | None:
    settings = get_settings()
    return build_object_storage(settings, bucket=settings.minio_public_bucket)


def public_storage() -> ObjectStorage | None:
    """Return the storage of the public bucket `events-public` (`None` when off)."""
    return _public_storage()


def scan_queue(request: Request) -> ScanQueue | None:
    """Return the scan queue on top of the arq pool (`None` without Redis)."""
    return scan_queue_from_pool(getattr(request.app.state, "arq_pool", None))


AttachmentStorage = Annotated[ObjectStorage | None, Depends(attachment_storage)]
PublicStorage = Annotated[ObjectStorage | None, Depends(public_storage)]
ScanQueueDep = Annotated[ScanQueue | None, Depends(scan_queue)]
