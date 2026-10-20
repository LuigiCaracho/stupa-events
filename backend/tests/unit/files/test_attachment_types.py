"""Upload validation: allowed types, hostile files and size limits (contract 3.1, 3.2)."""

from __future__ import annotations

import pytest

from app.modules.files.attachment_types import MAX_IMAGE_BYTES, check_attachment
from app.shared.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from tests._support import samples
from tests._support.factories import png_bytes


@pytest.mark.parametrize(
    ("kind", "name", "data", "mime"),
    [
        ("poster", "plakat.png", png_bytes(), "image/png"),
        ("quote", "angebot.pdf", samples.pdf_bytes(), "application/pdf"),
        ("contract", "vertrag.docx", samples.ooxml_bytes(".docx"), None),
        ("business_plan", "plan.xlsx", samples.ooxml_bytes(".xlsx"), None),
        ("howto_file", "ablauf.md", "# Ablauf\n\nÜberall Umlaute und €\n".encode(), None),
        ("other", "liste.csv", b"a;b\n1;2\n", None),
        ("other", "notiz.txt", b"hallo", None),
        ("other", "foto.png", png_bytes(), "image/png"),
    ],
)
def test_allowed_files_pass(kind: str, name: str, data: bytes, mime: str | None) -> None:
    checked = check_attachment(kind, name, data)
    assert mime is None or checked.mime == mime


@pytest.mark.parametrize(
    ("name", "data"),
    [
        ("grafik.svg", samples.svg_bytes()),
        ("grafik.png", samples.svg_bytes()),
        ("anim.gif", samples.gif_bytes()),
        ("alt.doc", samples.ole2_bytes()),
        ("makro.docm", samples.ooxml_bytes(".docx")),
        ("foto.png", samples.exe_bytes()),
        ("evil.exe", samples.exe_bytes()),
        ("macro.docx", samples.ooxml_bytes(".docx", macro=True)),
        ("fake.docx", b"PK\x03\x04 not a container"),
        ("binary.txt", b"abc\x00def"),
        ("latin.csv", "a;b\nÄ;ö\n".encode("latin-1")),
        ("page.md", b"<!DOCTYPE html><html><body><script>1</script></body></html>"),
    ],
)
def test_hostile_or_unknown_files_are_415(name: str, data: bytes) -> None:
    with pytest.raises(UnsupportedMediaTypeError) as caught:
        check_attachment("other", name, data)
    assert caught.value.status == 415 and caught.value.code == "unsupported_media_type"


def test_zip_bomb_and_entry_flood_are_archive_bombs() -> None:
    for data in (samples.zip_bomb_docx(), samples.many_entries_docx()):
        with pytest.raises(UnsupportedMediaTypeError) as caught:
            check_attachment("other", "x.docx", data)
        assert caught.value.code == "archive_bomb"


def test_pdf_with_javascript_is_active_content() -> None:
    with pytest.raises(UnsupportedMediaTypeError) as caught:
        check_attachment("quote", "a.pdf", samples.pdf_bytes(active=True))
    assert caught.value.code == "active_content"


@pytest.mark.parametrize(
    ("kind", "name", "data"),
    [
        ("poster", "a.pdf", samples.pdf_bytes()),
        ("social_post", "a.docx", samples.ooxml_bytes(".docx")),
        ("quote", "a.png", png_bytes()),
        ("contract", "a.png", png_bytes()),
        ("business_plan", "a.png", png_bytes()),
    ],
)
def test_images_and_documents_stay_in_their_kinds(kind: str, name: str, data: bytes) -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        check_attachment(kind, name, data)


def test_an_oversize_image_is_413_with_the_limit() -> None:
    data = png_bytes() + b"\x00" * (MAX_IMAGE_BYTES + 1)
    with pytest.raises(PayloadTooLargeError) as caught:
        check_attachment("other", "gross.png", data)
    assert caught.value.code == "file_too_large"
    assert caught.value.extensions == {"limitBytes": MAX_IMAGE_BYTES}
