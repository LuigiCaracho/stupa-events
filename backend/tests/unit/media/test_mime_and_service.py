"""MIME validation with a narrowed allowlist and the media service upload."""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.modules.files.mime import MimeRejected, validate_upload
from app.modules.media.models import POSTER_MIMES
from app.modules.media.refs import image_ids_in, image_path, is_image_path
from app.modules.media.service import MediaService
from app.shared.errors import (
    PayloadTooLargeError,
    ServiceUnavailableError,
    UnsupportedMediaTypeError,
)
from tests._support.factories import png_bytes
from tests._support.memory_storage import MemoryStorage


def test_validate_upload_accepts_a_png_and_checks_the_extension() -> None:
    assert validate_upload("p.png", png_bytes(), POSTER_MIMES) == "image/png"
    with pytest.raises(MimeRejected):
        validate_upload("p.jpg", png_bytes(), POSTER_MIMES)
    with pytest.raises(MimeRejected):
        validate_upload("p.png", png_bytes(), frozenset({"image/jpeg"}))
    with pytest.raises(MimeRejected):
        validate_upload("p.exe", png_bytes())


class _Session:
    def __init__(self) -> None:
        self.added: list[Any] = []
        self.committed = False

    def add(self, row: Any) -> None:
        self.added.append(row)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def get(self, model: Any, key: Any) -> Any:
        return next((r for r in self.added if r.id == key), None)


async def test_upload_stores_cleaned_bytes_and_row() -> None:
    session, storage = _Session(), MemoryStorage()
    service = MediaService(session, storage=storage)  # type: ignore[arg-type]
    out = await service.upload(png_bytes(64, 32))
    assert out.url == image_path(out.id)
    assert is_image_path(out.url)
    assert session.committed
    assert list(storage.blobs) == [session.added[0].storage_key]
    opened = await service.open(out.id)
    assert opened.mime == "image/png"
    assert (
        b"".join([chunk async for chunk in opened.stream])
        == storage.blobs[session.added[0].storage_key]
    )


async def test_upload_error_paths() -> None:
    with pytest.raises(ServiceUnavailableError):
        await MediaService(_Session(), storage=None).upload(png_bytes())  # type: ignore[arg-type]
    with pytest.raises(UnsupportedMediaTypeError):
        await MediaService(_Session(), storage=MemoryStorage()).upload(b"junk")  # type: ignore[arg-type]
    with pytest.raises(PayloadTooLargeError):
        await MediaService(  # type: ignore[arg-type]
            _Session(), storage=MemoryStorage(), max_bytes=10
        ).upload(png_bytes())


def test_image_refs_find_only_canonical_paths() -> None:
    one, two = uuid.uuid4(), uuid.uuid4()
    text = f"![a]({image_path(one)}) ![b](https://x/{one}) ![c]({image_path(two)}) ![d]({image_path(one)})"
    assert image_ids_in(text, None) == [one, two]
