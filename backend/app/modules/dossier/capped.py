"""A route class that reads the request body as a stream and stops with 413 above a limit.

Pattern from `events.drafts_router.CappedBodyRoute`, with the limit as a parameter.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.routing import APIRoute

from app.shared.errors import PayloadTooLargeError


def capped_route(max_bytes: int) -> type[APIRoute]:
    """Return a route class whose handler never sees a body above `max_bytes`."""

    class CappedBodyRoute(APIRoute):
        def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
            handler = super().get_route_handler()

            async def capped(request: Request) -> Response:
                declared = request.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise PayloadTooLargeError(f"The body exceeds {max_bytes} bytes.")
                body = bytearray()
                async for chunk in request.stream():
                    body += chunk
                    if len(body) > max_bytes:
                        raise PayloadTooLargeError(f"The body exceeds {max_bytes} bytes.")
                request._body = bytes(body)  # noqa: SLF001
                return await handler(request)

            return capped

    return CappedBodyRoute
