"""Poster cleaning and the public WebP derivatives."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.modules.media.derivatives import (
    DERIVATIVE_SPECS,
    derivative_id,
    derive_webp,
    parse_derivative_id,
)
from app.modules.media.images import ImageRejected, clean_image
from app.modules.media.models import POSTER_MIMES
from tests._support.factories import png_bytes


def _jpeg_with_exif() -> bytes:
    image = Image.new("RGB", (80, 40), "#aa3300")
    exif = Image.Exif()
    exif[0x010F] = "SecretCamera"
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()


def _gif() -> bytes:
    buffer = io.BytesIO()
    Image.new("P", (10, 10)).save(buffer, "GIF")
    return buffer.getvalue()


def test_clean_image_drops_exif() -> None:
    raw = _jpeg_with_exif()
    assert b"SecretCamera" in raw
    cleaned = clean_image(raw, POSTER_MIMES)
    assert cleaned.mime == "image/jpeg"
    assert b"SecretCamera" not in cleaned.data
    assert (cleaned.width, cleaned.height) == (80, 40)


def test_gif_is_no_poster() -> None:
    assert clean_image(_gif()).mime == "image/gif"
    with pytest.raises(ImageRejected):
        clean_image(_gif(), POSTER_MIMES)


@pytest.mark.parametrize(
    "data", [b"", b"not an image", b"<svg xmlns='http://www.w3.org/2000/svg'/>"]
)
def test_non_images_are_rejected(data: bytes) -> None:
    with pytest.raises(ImageRejected):
        clean_image(data, POSTER_MIMES)


def test_oversized_pixels_are_scaled_down() -> None:
    cleaned = clean_image(png_bytes(3000, 1500))
    assert max(cleaned.width, cleaned.height) == 2400


@pytest.mark.parametrize(
    ("variant", "size"),
    [("thumb_400", (400, 300)), ("card_1200", (1200, 675)), ("og_1200x630", (1200, 630))],
)
def test_derivative_sizes(variant: str, size: tuple[int, int]) -> None:
    result = derive_webp(png_bytes(800, 600), DERIVATIVE_SPECS[variant])
    assert result.mime == "image/webp"
    assert (result.width, result.height) == size
    with Image.open(io.BytesIO(result.data)) as decoded:
        assert decoded.format == "WEBP"
        assert not decoded.info.get("exif")


def test_derivative_refuses_non_poster_input() -> None:
    with pytest.raises(ImageRejected):
        derive_webp(_gif(), DERIVATIVE_SPECS["thumb_400"])


def test_derivative_ids_roundtrip_and_reject_garbage() -> None:
    sha = "3fa9c1d2e4b5a678" + "0" * 48
    identifier = derivative_id(sha, "card_1200")
    assert identifier == "3fa9c1d2e4b5a678-card_1200"
    assert parse_derivative_id(identifier) == ("3fa9c1d2e4b5a678", "card_1200")
    assert parse_derivative_id("../etc-card_1200") is None
    assert parse_derivative_id("3fa9c1d2e4b5a678-huge") is None
    with pytest.raises(ValueError):
        derivative_id(sha, "huge")
    with pytest.raises(ValueError):
        derivative_id("abc", "thumb_400")
