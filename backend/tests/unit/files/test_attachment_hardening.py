"""Heuristics of the upload check: hidden PDF actions, ODT macros, real archive size, MIME."""

from __future__ import annotations

import io
import struct
import zipfile
import zlib

import pytest

from app.modules.files.attachment_types import check_attachment
from app.shared.errors import UnsupportedMediaTypeError
from tests._support import samples

_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
_ODT = "application/vnd.oasis.opendocument.text"


def _pdf(catalog_extra: bytes = b"", stream: bytes | None = None) -> bytes:
    body = b"%PDF-1.5\n1 0 obj << /Type /Catalog /Pages 2 0 R " + catalog_extra + b" >> endobj\n"
    if stream is not None:
        body += b"3 0 obj << /Filter /FlateDecode >>\nstream\n" + zlib.compress(stream)
        body += b"\nendstream endobj\n"
    return (
        body + b"2 0 obj << /Type /Pages /Count 0 /Kids [] >> endobj\ntrailer << /Root 1 0 R >>\n"
    )


def _odt(extra: dict[str, bytes] | None = None, content: bytes = b"<office:document/>") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", _ODT, compress_type=zipfile.ZIP_STORED)
        archive.writestr("content.xml", content)
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return buffer.getvalue()


@pytest.mark.parametrize(
    "data",
    [
        _pdf(b"/Names << /J#61vaScript 4 0 R >>"),
        _pdf(b"/AA << /O 4 0 R >>"),
        _pdf(b"/OpenAction << /S /GoToR >>"),
        _pdf(b"/OpenAction 5 0 R"),
        _pdf(stream=b"<< /S /Launch /F (cmd.exe) >>"),
        _pdf(b"/AcroForm << /SubmitForm 1 0 R >>"),
        _pdf(b"/Kids [<< /Subtype /RichMedia >>]"),
    ],
)
def test_hidden_pdf_actions_are_active_content(data: bytes) -> None:
    with pytest.raises(UnsupportedMediaTypeError) as caught:
        check_attachment("quote", "a.pdf", data)
    assert caught.value.code == "active_content"


def test_a_plain_pdf_with_a_page_destination_passes() -> None:
    assert check_attachment("quote", "a.pdf", _pdf(b"/OpenAction [3 0 R /Fit]")).mime == (
        "application/pdf"
    )


@pytest.mark.parametrize(
    ("extra", "content"),
    [
        ({"Basic/Standard/Module1.xml": b"<x/>"}, b"<office:document/>"),
        ({"Scripts/python/a.py": b"print(1)"}, b"<office:document/>"),
        ({"Object 1/content.xml": b"<x/>"}, b"<office:document/>"),
        ({}, b'<office:document><script:event-listener script:language="x"/></office:document>'),
    ],
)
def test_odt_macros_are_415(extra: dict[str, bytes], content: bytes) -> None:
    with pytest.raises(UnsupportedMediaTypeError):
        check_attachment("other", "a.odt", _odt(extra, content))


def test_a_plain_odt_passes() -> None:
    assert check_attachment("other", "a.odt", _odt()).mime == _ODT


def test_a_declared_size_that_lies_does_not_hide_a_bomb() -> None:
    data = bytearray(samples.zip_bomb_docx())
    end = bytes(data).rfind(b"PK\x01\x02")
    while end != -1:
        name_len = struct.unpack_from("<H", data, end + 28)[0]
        if bytes(data[end + 46 : end + 46 + name_len]) == b"word/media/big.bin":
            struct.pack_into("<I", data, end + 24, 1000)
            break
        end = bytes(data).rfind(b"PK\x01\x02", 0, end)
    with pytest.raises(UnsupportedMediaTypeError):
        check_attachment("other", "x.docx", bytes(data))


def test_an_ooxml_file_keeps_its_ooxml_type() -> None:
    assert check_attachment("other", "a.docx", samples.ooxml_bytes(".docx")).mime == _DOCX
