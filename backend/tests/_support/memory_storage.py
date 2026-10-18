"""An in-memory object storage for tests: keeps the objects in a dict."""

from __future__ import annotations

from collections.abc import AsyncIterator


class MemoryStorage:
    """Object storage double; `remove` of a missing key does nothing."""

    def __init__(self) -> None:
        self.blobs: dict[str, bytes] = {}

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        self.blobs[key] = data

    async def get(self, key: str) -> bytes:
        return self.blobs[key]

    async def get_stream(self, key: str, *, chunk_size: int = 64 * 1024) -> AsyncIterator[bytes]:
        async def _iter() -> AsyncIterator[bytes]:
            yield self.blobs[key]

        return _iter()

    async def remove(self, key: str) -> None:
        self.blobs.pop(key, None)
