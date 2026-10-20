"""Images lose their metadata and bombs are refused (contract 3.2, 3.5; PLAN 18 Minor 4)."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.modules.dossier.derive import derive_webp
from app.modules.files.attachment_types import ATTACHMENT_IMAGE_MIMES
from app.modules.media.derivatives import DERIVATIVE_SPECS
from app.modules.media.images import ImageRejected, clean_image
from app.modules.media.preview import preview_webp
from app.shared.filenames import content_disposition
from tests._support import samples


def _exif_of(data: bytes) -> Image.Exif:
    with Image.open(io.BytesIO(data)) as image:
        return image.getexif()


def test_the_sample_really_carries_gps() -> None:
    assert _exif_of(samples.jpeg_with_gps()).get_ifd(0x8825)


def test_exif_gps_is_stripped_from_the_stored_file_the_preview_and_the_derivatives() -> None:
    cleaned = clean_image(samples.jpeg_with_gps(), ATTACHMENT_IMAGE_MIMES)
    assert b"Exif" not in cleaned.data[:64] and len(_exif_of(cleaned.data)) == 0
    assert len(_exif_of(preview_webp(cleaned.data).data)) == 0
    for spec in DERIVATIVE_SPECS.values():
        derived = derive_webp(cleaned.data, spec).data
        assert len(_exif_of(derived)) == 0 and b"EXIF" not in derived


def test_a_30000_px_png_is_a_rejected_bomb() -> None:
    bomb = samples.bomb_png()
    assert len(bomb) < 2 * 1024 * 1024
    with pytest.raises(ImageRejected):
        clean_image(bomb, ATTACHMENT_IMAGE_MIMES)


@pytest.mark.parametrize("name", ["Plakat 5 € 🎬.pdf", "Ärger mit Ü.pdf", "‮gpj.exe", ""])
def test_euro_emoji_and_bidi_names_make_a_valid_header(name: str) -> None:
    header = content_disposition("attachment", name)
    header.encode("ascii")
    assert "filename*=UTF-8''" in header and "\n" not in header
