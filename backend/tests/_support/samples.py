"""Byte samples for upload tests: documents, containers, hostile images, an EXIF-GPS JPEG."""

from __future__ import annotations

import io
import struct
import zipfile
import zlib

from app.modules.files.scanner import EICAR_TEST_BYTES

EICAR = EICAR_TEST_BYTES


def pdf_bytes(*, active: bool = False) -> bytes:
    """Return a tiny PDF, optionally with a `/JavaScript` action."""
    action = b"/OpenAction << /S /JavaScript /JS (app.alert(1)) >>" if active else b""
    return (
        b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R " + action + b" >> endobj\n"
        b"2 0 obj << /Type /Pages /Count 0 /Kids [] >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
    )


def ooxml_bytes(
    ext: str = ".docx", *, macro: bool = False, extra: dict[str, bytes] | None = None
) -> bytes:
    """Return a minimal OOXML container of `ext`, optionally with `vbaProject.bin`."""
    folder = {".docx": "word", ".xlsx": "xl", ".pptx": "ppt"}[ext]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        archive.writestr(f"{folder}/document.xml", "<w:document/>")
        if macro:
            archive.writestr(f"{folder}/vbaProject.bin", b"\xd0\xcf\x11\xe0")
        for name, data in (extra or {}).items():
            archive.writestr(name, data)
    return buffer.getvalue()


def zip_bomb_docx() -> bytes:
    """Return an OOXML container that unpacks to far more than 100 times its size."""
    return ooxml_bytes(extra={"word/media/big.bin": b"\x00" * (8 * 1024 * 1024)})


def many_entries_docx(count: int = 5001) -> bytes:
    """Return an OOXML container with more entries than the allowed 5000."""
    return ooxml_bytes(extra={f"word/media/{i}.txt": b"x" for i in range(count)})


def svg_bytes() -> bytes:
    """Return an SVG with a script."""
    return b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'


def gif_bytes() -> bytes:
    """Return a one-pixel GIF."""
    return b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"


def ole2_bytes() -> bytes:
    """Return the OLE2 header of a legacy `.doc` file."""
    return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 504


def exe_bytes() -> bytes:
    """Return a DOS/PE header."""
    return b"MZ\x90\x00\x03\x00\x00\x00" + b"\x00" * 120


def bomb_png(side: int = 30_000) -> bytes:
    """Return a valid PNG of `side` x `side` pixels that takes a few hundred KB (1-bit zeros)."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", side, side, 1, 0, 0, 0, 0)
    row = b"\x00" * (1 + (side + 7) // 8)
    packer = zlib.compressobj(9)
    data = b"".join(packer.compress(row) for _ in range(side)) + packer.flush()
    return (
        b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", data) + chunk(b"IEND", b"")
    )


def jpeg_with_gps(width: int = 1300, height: int = 800) -> bytes:
    """Return a JPEG whose EXIF carries a GPS block (Reutlingen)."""
    from PIL import Image

    exif = Image.Exif()
    exif[0x010F] = "TestCam"
    gps = exif.get_ifd(0x8825)
    gps[1], gps[2], gps[3], gps[4] = "N", (48.0, 29.0, 31.0), "E", (9.0, 12.0, 41.0)
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), "#cc3333").save(buffer, "JPEG", exif=exif)
    return buffer.getvalue()
