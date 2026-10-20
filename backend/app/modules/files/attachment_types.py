"""Which bytes an attachment of a given kind may be (M4 contract 3.1 and 3.2).

The sniffed content decides, never the client type. Images are PNG, JPEG and WebP up to
10 MiB; documents are PDF, OOXML, ODT and plain text up to 25 MiB. SVG, GIF, legacy
Office (OLE2), macro formats, archives and a wrong extension are always 415. OOXML and ODT
containers are opened as ZIP and checked for bombs (the real unpacked size is measured) and
macros, a PDF is searched for active content after `#xx` name escapes are resolved and Flate
streams unpacked. That PDF search is a heuristic and no protection of its own: ClamAV stays the
real net.
"""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from dataclasses import dataclass

from app.modules.files.mime import file_extension, sniff_mime
from app.shared.errors import PayloadTooLargeError, UnsupportedMediaTypeError

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_DOCUMENT_BYTES = 25 * 1024 * 1024
IMAGE_KINDS = frozenset({"poster", "social_post"})
DOCUMENT_ONLY_KINDS = frozenset({"business_plan", "quote", "contract"})

ATTACHMENT_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/webp"})
_OOXML = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
_OOXML_DIR = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}
_TEXT_SNIFFS = frozenset({"text/plain", "text/csv", "text/markdown", "application/csv"})
_EXTENSION_SNIFFS: dict[str, frozenset[str]] = {
    ".png": frozenset({"image/png"}),
    ".jpg": frozenset({"image/jpeg"}),
    ".jpeg": frozenset({"image/jpeg"}),
    ".webp": frozenset({"image/webp"}),
    ".pdf": frozenset({"application/pdf"}),
    ".odt": frozenset({"application/vnd.oasis.opendocument.text"}),
    ".md": _TEXT_SNIFFS,
    ".txt": _TEXT_SNIFFS,
    ".csv": _TEXT_SNIFFS,
    **{ext: frozenset({mime, "application/zip"}) for ext, mime in _OOXML.items()},
}
ATTACHMENT_EXTENSIONS = frozenset(_EXTENSION_SNIFFS)
_DOC_ONLY_MIMES = frozenset(
    {"application/pdf", "application/vnd.oasis.opendocument.text", "application/zip"}
    | set(_OOXML.values())
    | _TEXT_SNIFFS
)

MAX_ZIP_ENTRIES = 5000
MAX_ZIP_UNPACKED = 200 * 1024 * 1024
MAX_ZIP_RATIO = 100
_CHUNK = 64 * 1024
_ACTIVE_PDF = re.compile(
    rb"/(JavaScript|JS|Launch|EmbeddedFile|AA|SubmitForm|ImportData|GoToR|GoToE|RichMedia)"
    rb"(?![A-Za-z0-9])|/OpenAction(?!\s*\[)"
)
_NAME_ESCAPE = re.compile(rb"#([0-9A-Fa-f]{2})")
_STREAM = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_ODT_ACTIVE = (b"<script:", b"vnd.sun.star.script:")
_ODT_ACTIVE_DIRS = ("Basic/", "Scripts/", "Object ")


@dataclass(frozen=True, slots=True)
class Checked:
    """The verdict on an upload: its sniffed type and whether it is an image."""

    mime: str
    is_image: bool


def _reject(detail: str, code: str = "unsupported_media_type") -> UnsupportedMediaTypeError:
    return UnsupportedMediaTypeError(detail, code=code)


def _real_size(archive: zipfile.ZipFile, infos: list[zipfile.ZipInfo], packed: int) -> int:
    limit = min(MAX_ZIP_UNPACKED, MAX_ZIP_RATIO * max(packed, 1))
    total = 0
    for info in infos:
        with archive.open(info) as entry:
            while chunk := entry.read(_CHUNK):
                total += len(chunk)
                if total > limit:
                    raise _reject(
                        "The document container looks like an archive bomb.", "archive_bomb"
                    )
    return total


def _check_odt_macros(archive: zipfile.ZipFile, names: list[str]) -> None:
    if any(n.startswith(_ODT_ACTIVE_DIRS) for n in names):
        raise _reject("Documents with macros are not accepted.")
    content = archive.read("content.xml") if "content.xml" in names else b""
    if any(marker in content for marker in _ODT_ACTIVE):
        raise _reject("Documents with macros are not accepted.")


def _check_zip(data: bytes, ext: str) -> None:
    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise _reject("The document container is damaged.") from exc
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise _reject("The document container looks like an archive bomb.", "archive_bomb")
        try:
            _real_size(archive, infos, len(data))
        except (zipfile.BadZipFile, zlib.error, NotImplementedError) as exc:
            raise _reject("The document container is damaged.") from exc
        names = [i.filename for i in infos]
        if ext in _OOXML_DIR and (
            "[Content_Types].xml" not in names
            or not any(n.startswith(_OOXML_DIR[ext]) for n in names)
        ):
            raise _reject(f"The file is no valid {ext} document.")
        if any(n.lower().endswith("vbaproject.bin") for n in names):
            raise _reject("Documents with macros are not accepted.")
        if "[Content_Types].xml" in names and b"macroEnabled" in archive.read(
            "[Content_Types].xml"
        ):
            raise _reject("Documents with macros are not accepted.")
        if ext == ".odt":
            _check_odt_macros(archive, names)


def _inflate(raw: bytes) -> bytes:
    unpacker = zlib.decompressobj()
    try:
        return unpacker.decompress(raw, MAX_DOCUMENT_BYTES)
    except zlib.error:
        return b""


def _has_active_pdf_content(data: bytes) -> bool:
    plain = _NAME_ESCAPE.sub(lambda m: bytes([int(m.group(1), 16)]), data)
    if _ACTIVE_PDF.search(plain):
        return True
    return any(_ACTIVE_PDF.search(_inflate(m.group(1))) for m in _STREAM.finditer(data))


def _check_text(data: bytes) -> None:
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _reject("Text files must be UTF-8.") from exc
    if b"\x00" in data:
        raise _reject("Text files must not contain NUL bytes.")


def _kind_accepts(kind: str, mime: str) -> bool:
    if kind in IMAGE_KINDS:
        return mime in ATTACHMENT_IMAGE_MIMES
    if kind in DOCUMENT_ONLY_KINDS:
        return mime in _DOC_ONLY_MIMES
    return True


def check_attachment(kind: str, filename: str | None, data: bytes) -> Checked:
    """Validate an upload of `kind` and return its sniffed type.

    Raises:
        UnsupportedMediaTypeError: Type, extension, container or content is not accepted.
        PayloadTooLargeError: The size exceeds the limit of its type (413, `limitBytes`).
    """
    ext = file_extension(filename)
    sniffed = sniff_mime(data)
    allowed = _EXTENSION_SNIFFS.get(ext)
    if allowed is None:
        raise _reject(f"Unsupported file extension: {ext or '(none)'}")
    if sniffed not in allowed:
        raise _reject(f"Content type '{sniffed}' does not match extension '{ext}'.")
    is_image = sniffed in ATTACHMENT_IMAGE_MIMES
    if not _kind_accepts(kind, sniffed):
        raise _reject(f"A {kind} cannot be a '{sniffed}' file.")
    limit = MAX_IMAGE_BYTES if is_image else MAX_DOCUMENT_BYTES
    if len(data) > limit:
        raise PayloadTooLargeError(
            f"The file exceeds {limit} bytes.",
            code="file_too_large",
            extensions={"limitBytes": limit},
        )
    if sniffed == "application/zip" or ext == ".odt" or ext in _OOXML_DIR:
        _check_zip(data, ext)
    elif sniffed == "application/pdf" and _has_active_pdf_content(data):
        raise _reject("PDF files with active content are not accepted.", "active_content")
    elif sniffed in _TEXT_SNIFFS:
        _check_text(data)
    return Checked(
        mime=_OOXML.get(ext, sniffed) if sniffed == "application/zip" else sniffed,
        is_image=is_image,
    )
