"""Private WebP preview of an uploaded image: 400 px on the long edge, no metadata."""

from __future__ import annotations

import io
from typing import Final

from app.modules.media.images import CleanImage, ImageRejected

PREVIEW_EDGE: Final[int] = 400
PREVIEW_QUALITY: Final[int] = 80


def preview_webp(data: bytes) -> CleanImage:
    """Encode `data` as a WebP whose long edge is at most `PREVIEW_EDGE` pixels.

    Raises:
        ImageRejected: The bytes cannot be decoded.
    """
    from PIL import Image, ImageOps

    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except (OSError, ValueError) as exc:
        raise ImageRejected(f"The image cannot be decoded ({type(exc).__name__}).") from exc
    image.thumbnail((PREVIEW_EDGE, PREVIEW_EDGE), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=PREVIEW_QUALITY)
    return CleanImage(
        data=buffer.getvalue(), mime="image/webp", width=image.width, height=image.height
    )
