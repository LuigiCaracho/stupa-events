"""Public WebP derivatives of a poster and their ids.

`derive_webp` decodes a stored poster again, cuts it to the target size and encodes WebP
without any metadata. The three variants of the public bucket are `thumb_400` (400 px
wide, aspect kept), `card_1200` (1200x675) and `og_1200x630` (1200x630). A fixed size
cuts the image to cover the box around the centre. The public id of a derivative is
`<sha256[:16]>-<variant>`, so a replaced poster gets new ids.

The module imports Pillow lazily, like `images`.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Final

from app.modules.files.mime import sniff_mime
from app.modules.media.images import CleanImage, ImageRejected
from app.modules.media.models import POSTER_MIMES

WEBP_QUALITY: Final[int] = 82
SHA_PREFIX_LENGTH: Final[int] = 16


@dataclass(frozen=True, slots=True)
class DerivativeSpec:
    """Target size of one variant; `height` is `None` for a width-only scale."""

    width: int
    height: int | None = None


DERIVATIVE_SPECS: Final[dict[str, DerivativeSpec]] = {
    "thumb_400": DerivativeSpec(400),
    "card_1200": DerivativeSpec(1200, 675),
    "og_1200x630": DerivativeSpec(1200, 630),
}

_ID_RE: Final = re.compile(rf"^([0-9a-f]{{{SHA_PREFIX_LENGTH}}})-({'|'.join(DERIVATIVE_SPECS)})$")


def derivative_id(sha256_hex: str, variant: str) -> str:
    """Return the public id `<sha256[:16]>-<variant>` of a derivative.

    Raises:
        ValueError: The variant is unknown or the digest is too short.
    """
    if variant not in DERIVATIVE_SPECS:
        raise ValueError(f"unknown variant: {variant}")
    if len(sha256_hex) < SHA_PREFIX_LENGTH:
        raise ValueError("sha256 digest too short")
    return f"{sha256_hex[:SHA_PREFIX_LENGTH]}-{variant}"


def parse_derivative_id(value: str) -> tuple[str, str] | None:
    """Split a public derivative id into `(sha_prefix, variant)`, or `None` if malformed."""
    match = _ID_RE.fullmatch(value)
    return (match.group(1), match.group(2)) if match else None


def derive_webp(data: bytes, spec: DerivativeSpec) -> CleanImage:
    """Encode `data` as a WebP of the size in `spec`, without metadata.

    Args:
        data: The stored poster bytes (PNG, JPEG or WebP).
        spec: The target size of the variant.

    Returns:
        The WebP bytes with the final width and height.

    Raises:
        ImageRejected: The bytes are no still image or cannot be decoded.
    """
    from PIL import Image, ImageOps

    if sniff_mime(data) not in POSTER_MIMES:
        raise ImageRejected("Poster derivatives need a PNG, JPEG or WebP image.")
    try:
        with Image.open(io.BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source).convert("RGBA")
    except (OSError, ValueError) as exc:
        raise ImageRejected(f"The image cannot be decoded ({type(exc).__name__}).") from exc
    if spec.height is None:
        height = max(1, round(image.height * spec.width / image.width))
        image = image.resize((spec.width, height), Image.Resampling.LANCZOS)
    else:
        image = ImageOps.fit(
            image, (spec.width, spec.height), Image.Resampling.LANCZOS, centering=(0.5, 0.5)
        )
    buffer = io.BytesIO()
    image.save(buffer, "WEBP", quality=WEBP_QUALITY)
    return CleanImage(
        data=buffer.getvalue(), mime="image/webp", width=image.width, height=image.height
    )
