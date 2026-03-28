"""Apple Pages document processor.

Modern ``.pages`` files are ZIP-based iWork packages containing protobuf-like
``.iwa`` archives, metadata plists, previews, and embedded assets. Apple does
not publish the complete schema for Pages archives, so this processor uses a
best-effort strategy similar to the existing Numbers and Keynote processors:

* inspect the ZIP package directly
* decompress IWA chunks with Snappy when available
* heuristically walk protobuf wire data to recover text and metadata
* extract embedded images from ``Data/``
* read ``preview.jpg`` (or similar preview images)
* fall back to macOS ``textutil`` when native extraction is sparse

The goal is practical extraction for indexing, accessibility, and conversion
workflows rather than exact round-trip fidelity.
"""

from __future__ import annotations

import logging
import math
import mimetypes
import platform
import plistlib
import re
import shutil
import struct
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    import snappy

    SNAPPY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    snappy = None
    SNAPPY_AVAILABLE = False

from .exceptions import DocumentValidationError, InvalidDocumentStructureError
from .models import (
    DocumentContent,
    DocumentStyle,
    Image,
    Metadata,
    OfficeFormat,
    Paragraph,
    Table,
    TableCell,
    TextRun,
)

logger = logging.getLogger(__name__)

IWA_MAGIC = b"IWA1"
PROTOBUF_VARINT_MAX = 10
SNAPPY_STREAM_IDENTIFIER = b"\xff\x06\x00\x00sNaPpY"
MAX_PROTO_DEPTH = 5
TEXTUTIL_TIMEOUT = 30
PDF_TIMEOUT = 90
MAX_TEXT_LENGTH = 4096
MAX_TABLE_COLUMNS = 16
DEFAULT_PARAGRAPH_STYLE = DocumentStyle(
    font_family="Helvetica Neue",
    font_size=12.0,
)
DEFAULT_HEADING_STYLE = DocumentStyle(
    font_family="Helvetica Neue",
    font_size=18.0,
    bold=True,
)
PRINTABLE_RUN_RE = re.compile(rb"[\x09\x0A\x0D\x20-\x7E]{4,}")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$")
DELIMITER_CANDIDATES = ("\t", "|", ",", ";")
IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".heic",
    ".webp",
    ".pdf",
    ".svg",
}
SYSTEMISH_STRINGS = {
    "Pages",
    "Document",
    "Document.iwa",
    "DocumentStylesheet.iwa",
    "Index",
    "Data",
    "Preview",
    "QuickLook",
    "TableModel",
    "Stylesheet",
}
NOISE_PREFIXES = ("Index/", "Data/", "QuickLook/", "Metadata/")


class PagesError(Exception):
    """Base exception for Pages processor errors."""


class PagesNotFoundError(PagesError):
    """Raised when a Pages file does not exist."""


class PagesCorruptedError(PagesError):
    """Raised when a Pages package is invalid or unreadable."""


class PagesUnsupportedError(PagesError):
    """Raised when a Pages feature is unavailable in the current environment."""


@dataclass(slots=True)
class _ProtoField:
    """One decoded protobuf field."""

    number: int
    wire_type: int
    value: Any


@dataclass(slots=True)
class _DecodedBytes:
    """Decoded length-delimited protobuf field."""

    raw: bytes
    text: str | None = None
    message: list[_ProtoField] | None = None


class _IWAParser:
    """Parse raw iWork Archive payloads into message blobs."""

    def __init__(self, data: bytes):
        self._data = data

    def parse(self) -> list[bytes]:
        """Return decompressed payload messages from an IWA container."""

        if not self._data:
            return []

        raw = self._data[4:] if self._data[:4] == IWA_MAGIC else self._data
        messages: list[bytes] = []
        position = 0

        while position < len(raw):
            try:
                chunk_size, position = _read_varint(raw, position)
            except ValueError:
                break

            if chunk_size <= 0 or position + chunk_size > len(raw):
                break

            chunk = raw[position : position + chunk_size]
            position += chunk_size
            message = self._decompress_chunk(chunk)
            if message:
                messages.append(message)

        if messages:
            return messages

        whole = self._decompress_chunk(raw)
        return [whole] if whole else [raw]

    def _decompress_chunk(self, chunk: bytes) -> bytes:
        if not chunk:
            return b""

        if chunk.startswith(SNAPPY_STREAM_IDENTIFIER):
            try:
                return self._decompress_framed_snappy(chunk)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Framed snappy decode failed: %s", exc)

        if SNAPPY_AVAILABLE and snappy is not None:
            for candidate in (chunk, _strip_possible_iwa_header(chunk)):
                if not candidate:
                    continue
                try:
                    return snappy.decompress(candidate)
                except Exception:
                    pass
                try:
                    return snappy.StreamDecompressor().decompress(candidate)
                except Exception:
                    pass

        return chunk

    def _decompress_framed_snappy(self, chunk: bytes) -> bytes:
        if not SNAPPY_AVAILABLE or snappy is None:
            return chunk

        output = bytearray()
        position = len(SNAPPY_STREAM_IDENTIFIER)

        while position + 4 <= len(chunk):
            chunk_type = chunk[position]
            length = int.from_bytes(chunk[position + 1 : position + 4], "little")
            position += 4
            data = chunk[position : position + length]
            position += length

            if not data:
                continue
            if chunk_type == 0x00:
                output.extend(snappy.decompress(data[4:]))
            elif chunk_type == 0x01:
                output.extend(data[4:])
            elif chunk_type == 0xFF:
                continue
            elif 0x80 <= chunk_type <= 0xFE:
                continue

        return bytes(output)


class _ProtoDecoder:
    """Schema-less protobuf decoder for Pages IWA payloads."""

    def decode(self, data: bytes, depth: int = 0) -> list[_ProtoField]:
        if depth > MAX_PROTO_DEPTH or not data:
            return []

        fields: list[_ProtoField] = []
        position = 0

        while position < len(data):
            try:
                key, position = _read_varint(data, position)
            except ValueError:
                break

            if key == 0:
                break

            field_number = key >> 3
            wire_type = key & 0x07

            try:
                value, position = self._read_value(data, position, wire_type, depth)
            except ValueError:
                break

            fields.append(_ProtoField(number=field_number, wire_type=wire_type, value=value))

        return fields

    def _read_value(
        self,
        data: bytes,
        position: int,
        wire_type: int,
        depth: int,
    ) -> tuple[Any, int]:
        if wire_type == 0:
            return _read_varint(data, position)

        if wire_type == 1:
            if position + 8 > len(data):
                raise ValueError("Truncated 64-bit field")
            raw = data[position : position + 8]
            position += 8
            int_value = int.from_bytes(raw, "little")
            float_value = struct.unpack("<d", raw)[0]
            return _pick_numeric_value(int_value, float_value), position

        if wire_type == 2:
            length, position = _read_varint(data, position)
            end = position + length
            if end > len(data):
                raise ValueError("Truncated length-delimited field")

            blob = data[position:end]
            position = end
            text = _try_decode_text(blob)
            nested = None
            if _looks_like_nested_protobuf(blob):
                nested = self.decode(blob, depth + 1) or None
            return _DecodedBytes(raw=blob, text=text, message=nested), position

        if wire_type == 5:
            if position + 4 > len(data):
                raise ValueError("Truncated 32-bit field")
            raw = data[position : position + 4]
            position += 4
            int_value = int.from_bytes(raw, "little")
            float_value = struct.unpack("<f", raw)[0]
            return _pick_numeric_value(int_value, float_value), position

        raise ValueError(f"Unsupported wire type: {wire_type}")


class PagesProcessor:
    """Parse, inspect, and export Apple Pages documents."""

    def __init__(
        self,
        *,
        use_textutil_fallback: bool | None = None,
        use_pages_automation: bool | None = None,
    ) -> None:
        self.is_macos = platform.system() == "Darwin"
        self.use_textutil_fallback = (
            self.is_macos if use_textutil_fallback is None else use_textutil_fallback
        )
        self.use_pages_automation = (
            self.is_macos if use_pages_automation is None else use_pages_automation
        )
        self._decoder = _ProtoDecoder()
        self._source_path: Path | None = None
        self._document: DocumentContent | None = None
        self._preview_image: bytes | None = None

    def parse(self, path: Path | str) -> DocumentContent:
        """Parse a Pages package into the shared office document model."""

        source = self._validate_path(Path(path))

        try:
            with zipfile.ZipFile(source, "r") as archive:
                document_messages = self._read_iwa_messages(archive, "Index/Document.iwa")
                index_strings = self._extract_index_strings(archive, document_messages)
                paragraphs = self._extract_paragraphs(index_strings)
                tables = self._extract_tables_from_archive(archive)
                images = self._extract_image_assets(archive)
                preview = self._extract_preview(archive)
                metadata = self._extract_metadata_from_archive(
                    archive,
                    source,
                    index_strings=index_strings,
                )
        except zipfile.BadZipFile as exc:
            raise PagesCorruptedError(f"Invalid Pages ZIP package: {source}") from exc

        fallback_used = False
        if self._should_use_textutil_fallback(paragraphs, tables):
            try:
                fallback_text = self._extract_text_with_textutil(source)
            except Exception as exc:  # pragma: no cover - platform dependent
                logger.debug("Pages textutil fallback failed: %s", exc)
            else:
                fallback_paragraphs = self._paragraphs_from_text(fallback_text)
                if fallback_paragraphs:
                    paragraphs = fallback_paragraphs
                    fallback_used = True

        document = DocumentContent(
            format=OfficeFormat.PAGES,
            paragraphs=paragraphs,
            tables=tables,
            images=images,
            metadata=metadata,
            styles={
                "heading": DEFAULT_HEADING_STYLE,
                "paragraph": DEFAULT_PARAGRAPH_STYLE,
            },
            document_properties={
                "paragraph_count": len(paragraphs),
                "table_count": len(tables),
                "image_count": len(images),
                "preview_available": preview is not None,
                "snappy_available": SNAPPY_AVAILABLE,
                "textutil_fallback_used": fallback_used,
            },
            resources={"preview.jpg": preview} if preview is not None else {},
        )

        self._source_path = source
        self._document = document
        self._preview_image = preview
        return document

    def extract_text(self, path: Path | str | None = None) -> str:
        """Return flattened text from the parsed Pages document.

        For backward compatibility this method also accepts a path and will parse
        the document on demand when provided.
        """

        document = self._ensure_document(path)
        parts = [
            self._paragraph_text(paragraph).strip()
            for paragraph in document.paragraphs
            if self._paragraph_text(paragraph).strip()
        ]

        if not parts:
            for table in document.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text_content().strip() for cell in row if cell.text_content().strip())
                    if row_text:
                        parts.append(row_text)

        return "\n\n".join(parts)

    def extract_tables(self, path: Path | str | None = None) -> list[Table]:
        """Return extracted Pages tables."""

        return list(self._ensure_document(path).tables)

    def extract_images(self, path: Path | str | None = None) -> list[Image]:
        """Return embedded image assets."""

        return list(self._ensure_document(path).images)

    def get_preview(self, path: Path | str | None = None) -> bytes | None:
        """Return preview image bytes if the package contains a preview."""

        self._ensure_document(path)
        return self._preview_image

    def get_preview_image(self, path: Path | str | None = None) -> bytes | None:
        """Backward-compatible alias for :meth:`get_preview`."""

        return self.get_preview(path)

    def get_metadata(self, path: Path | str | None = None) -> Metadata:
        """Return parsed Pages document metadata."""

        return self._ensure_document(path).metadata

    def extract_metadata(self, path: Path | str | None = None) -> Metadata:
        """Backward-compatible alias for :meth:`get_metadata`."""

        return self.get_metadata(path)

    def to_pdf(self, *args: Path | str) -> Path:
        """Export the Pages document to PDF on macOS.

        Supported call styles:

        * ``to_pdf(output_path)`` after ``parse(path)``
        * ``to_pdf(input_path, output_path)`` for one-shot conversion
        """

        if len(args) == 1:
            source = self._source_path
            if source is None:
                raise PagesError("Call parse(path) before to_pdf(output_path)")
            output_path = Path(args[0])
        elif len(args) == 2:
            source = self._validate_path(Path(args[0]))
            output_path = Path(args[1])
            self._source_path = source
        else:
            raise TypeError("to_pdf expects (output_path) or (input_path, output_path)")

        assert source is not None
        destination = output_path.expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        if not self.is_macos:
            raise PagesUnsupportedError("Pages PDF export requires macOS")

        last_error: Exception | None = None

        if self.use_textutil_fallback:
            try:
                if self._export_pdf_with_textutil(source, destination):
                    return destination
            except Exception as exc:  # pragma: no cover - platform dependent
                last_error = exc
                logger.debug("Pages textutil PDF export failed: %s", exc)

        if self.use_pages_automation:
            try:
                return self._export_pdf_with_pages_automation(source, destination)
            except Exception as exc:  # pragma: no cover - platform dependent
                last_error = exc
                logger.debug("Pages automation PDF export failed: %s", exc)

        if last_error is not None:
            raise InvalidDocumentStructureError(
                f"Unable to export Pages document to PDF: {last_error}"
            ) from last_error
        raise InvalidDocumentStructureError("Unable to export Pages document to PDF")

    def _ensure_document(self, path: Path | str | None = None) -> DocumentContent:
        if path is not None:
            requested = Path(path).expanduser().resolve()
            if self._document is None or self._source_path != requested:
                return self.parse(requested)
        if self._document is None:
            raise PagesError("No Pages document has been parsed yet. Call parse(path) first.")
        return self._document

    def _validate_path(self, path: Path) -> Path:
        source = path.expanduser().resolve()
        if not source.exists():
            raise PagesNotFoundError(f"File not found: {source}")
        if not source.is_file():
            raise PagesUnsupportedError(f"Pages path is not a file: {source}")
        if source.suffix.lower() != ".pages":
            raise PagesUnsupportedError(
                f"Expected a .pages file, got: {source.suffix or '<no extension>'}"
            )
        if not zipfile.is_zipfile(source):
            raise PagesCorruptedError(f"Not a valid Pages ZIP package: {source}")
        return source

    def _read_iwa_messages(self, archive: zipfile.ZipFile, name: str) -> list[bytes]:
        try:
            payload = archive.read(name)
        except KeyError:
            return []
        return _IWAParser(payload).parse()

    def _extract_index_strings(
        self,
        archive: zipfile.ZipFile,
        document_messages: Sequence[bytes],
    ) -> list[str]:
        strings: list[str] = []

        if document_messages:
            for message in document_messages:
                strings.extend(self._strings_from_message(message))
        else:
            strings.extend(self._package_strings(archive, include_tables=False))

        for name in archive.namelist():
            if not name.startswith("Index/") or not name.endswith(".iwa"):
                continue
            if name == "Index/Document.iwa" or "/Tables/" in name:
                continue
            for message in self._read_iwa_messages(archive, name):
                strings.extend(self._strings_from_message(message))

        return self._clean_text_values(strings)

    def _extract_paragraphs(self, index_strings: Sequence[str]) -> list[Paragraph]:
        if not index_strings:
            return []

        paragraphs: list[Paragraph] = []
        for value in index_strings:
            for paragraph_text in self._split_paragraph_candidates(value):
                paragraph = self._make_paragraph(paragraph_text)
                if paragraph is not None:
                    paragraphs.append(paragraph)

        return self._dedupe_paragraphs(paragraphs)

    def _extract_tables_from_archive(self, archive: zipfile.ZipFile) -> list[Table]:
        table_names = [
            name
            for name in archive.namelist()
            if name.startswith("Index/Tables/") and name.endswith(".iwa")
        ]
        table_names.sort(key=self._natural_sort_key)

        tables: list[Table] = []
        for index, name in enumerate(table_names, start=1):
            try:
                messages = self._read_iwa_messages(archive, name)
            except Exception as exc:
                logger.debug("Failed to read table archive %s: %s", name, exc)
                continue

            rows = self._rows_from_table_messages(messages)
            if not rows:
                continue

            tables.append(
                Table(
                    rows=rows,
                    has_header_row=len(rows) > 1 and all(cell.text_content().strip() for cell in rows[0]),
                    table_id=f"table-{index}",
                )
            )

        return tables

    def _rows_from_table_messages(self, messages: Sequence[bytes]) -> list[list[TableCell]]:
        delimited_rows: list[list[str]] = []
        row_candidates: list[list[str]] = []

        for message in messages:
            fields = self._decoder.decode(message)
            strings = self._clean_text_values(_collect_strings(fields))
            if not strings:
                strings = self._clean_text_values(_extract_printable_runs(message))
            if not strings:
                continue

            delimited_rows.extend(self._delimited_rows_from_strings(strings))

            compact = [value for value in strings if "\n" not in value][:MAX_TABLE_COLUMNS]
            if 1 < len(compact) <= MAX_TABLE_COLUMNS:
                row_candidates.append(compact)

        if delimited_rows:
            return [self._cells_from_values(row) for row in delimited_rows]

        if row_candidates:
            return [self._cells_from_values(row) for row in row_candidates]

        flattened: list[str] = []
        for message in messages:
            flattened.extend(self._clean_text_values(self._strings_from_message(message)))

        flattened = flattened[:MAX_TABLE_COLUMNS * 32]
        if len(flattened) < 2:
            return []

        width = min(MAX_TABLE_COLUMNS, max(2, int(math.sqrt(len(flattened)))))
        rows: list[list[TableCell]] = []
        for start in range(0, len(flattened), width):
            rows.append(self._cells_from_values(flattened[start : start + width]))
        return rows

    def _extract_image_assets(self, archive: zipfile.ZipFile) -> list[Image]:
        images: list[Image] = []

        for name in archive.namelist():
            path = Path(name)
            if not name.startswith("Data/") or path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue

            mime_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
            try:
                payload = archive.read(name)
            except KeyError:
                continue

            images.append(
                Image(
                    data=payload,
                    mime_type=mime_type,
                    title=path.name,
                    description=f"Embedded Pages asset: {path.name}",
                    properties={
                        "internal_path": name,
                        "extension": path.suffix.lower(),
                    },
                )
            )

        return images

    def _extract_preview(self, archive: zipfile.ZipFile) -> bytes | None:
        for candidate in ("preview.jpg", "preview.jpeg", "QuickLook/Preview.jpg"):
            if candidate in archive.namelist():
                return archive.read(candidate)

        preview_names = [
            name
            for name in archive.namelist()
            if "preview" in name.lower()
            and Path(name).suffix.lower() in {".jpg", ".jpeg", ".png"}
        ]
        preview_names.sort(key=self._natural_sort_key)
        if not preview_names:
            return None
        return archive.read(preview_names[0])

    def _extract_metadata_from_archive(
        self,
        archive: zipfile.ZipFile,
        source: Path,
        *,
        index_strings: Sequence[str],
    ) -> Metadata:
        metadata = Metadata(
            title=source.stem,
            modified_at=datetime.fromtimestamp(source.stat().st_mtime, tz=UTC),
        )

        for name in archive.namelist():
            if not name.lower().endswith(".plist"):
                continue
            try:
                payload = plistlib.loads(archive.read(name))
            except Exception:
                logger.debug("Failed to parse plist metadata from %s", name)
                continue
            self._apply_plist_metadata(metadata, payload, origin=name)

        if "Index/Document.iwa" in archive.namelist():
            try:
                document_strings = self._clean_text_values(
                    self._strings_from_payload(archive.read("Index/Document.iwa"))
                )
            except Exception:
                document_strings = list(index_strings)
        else:
            document_strings = list(index_strings)

        inferred_title = self._extract_title(document_strings)
        if inferred_title and (metadata.title is None or metadata.title == source.stem):
            metadata.title = inferred_title

        author_hint = _extract_authorish_string(document_strings)
        if author_hint and metadata.author is None:
            metadata.author = author_hint

        app_version = _extract_pages_app_version(document_strings)
        if app_version is not None:
            metadata.custom_properties.setdefault("app_version", app_version)

        metadata.custom_properties.setdefault("archive_entry_count", len(archive.namelist()))
        metadata.custom_properties.setdefault("preview_available", self._extract_preview(archive) is not None)
        return metadata

    def _apply_plist_metadata(self, metadata: Metadata, value: Any, *, origin: str) -> None:
        for key, item in self._flatten_plist(value).items():
            normalized = key.lower()
            if metadata.title is None and normalized.endswith(("title", "documenttitle")):
                metadata.title = str(item)
            elif metadata.author is None and normalized.endswith(("author", "creator")):
                metadata.author = str(item)
            elif metadata.subject is None and normalized.endswith(("subject", "description")):
                metadata.subject = str(item)
            elif metadata.company is None and normalized.endswith("company"):
                metadata.company = str(item)
            elif normalized.endswith(("category",)):
                metadata.category = metadata.category or str(item)
            elif normalized.endswith(("keyword", "keywords", "tag", "tags")) and isinstance(item, str):
                metadata.keywords.extend(
                    part.strip()
                    for part in re.split(r"[;,]", item)
                    if part.strip()
                )
            elif metadata.created_at is None and normalized.endswith(("created", "creationdate")):
                converted = self._coerce_datetime(item)
                if converted is not None:
                    metadata.created_at = converted
            elif metadata.modified_at is None and normalized.endswith(("modified", "modificationdate")):
                converted = self._coerce_datetime(item)
                if converted is not None:
                    metadata.modified_at = converted

            scalar = self._coerce_scalar(item)
            if scalar is not None:
                metadata.custom_properties[f"{origin}:{key}"] = scalar

        metadata.keywords = _dedupe_preserve_order(metadata.keywords)

    def _extract_text_with_textutil(self, path: Path) -> str:
        if not self.is_macos or not self.use_textutil_fallback:
            return ""
        textutil_path = shutil.which("textutil")
        if textutil_path is None:
            return ""

        result = subprocess.run(
            [textutil_path, "-convert", "txt", "-stdout", str(path)],
            capture_output=True,
            text=True,
            timeout=TEXTUTIL_TIMEOUT,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""

    def _export_pdf_with_textutil(self, source: Path, output_path: Path) -> bool:
        textutil_path = shutil.which("textutil")
        if textutil_path is None:
            return False

        result = subprocess.run(
            [textutil_path, "-convert", "pdf", "-output", str(output_path), str(source)],
            capture_output=True,
            text=True,
            timeout=PDF_TIMEOUT,
            check=False,
        )
        return result.returncode == 0 and output_path.exists()

    def _export_pdf_with_pages_automation(self, source: Path, output_path: Path) -> Path:
        if shutil.which("osascript") is None:
            raise DocumentValidationError("osascript is not available for Pages automation")

        escaped_input = self._escape_applescript_string(str(source))
        escaped_output = self._escape_applescript_string(str(output_path))
        applescript = f"""
        tell application "Pages"
            set docRef to open POSIX file "{escaped_input}"
            delay 1
            export docRef to POSIX file "{escaped_output}" as PDF
            close docRef saving no
        end tell
        """
        result = subprocess.run(
            ["osascript", "-e", applescript],
            capture_output=True,
            text=True,
            timeout=PDF_TIMEOUT,
            check=False,
        )
        if result.returncode != 0:
            raise InvalidDocumentStructureError(
                result.stderr.strip() or result.stdout.strip() or "Pages automation export failed"
            )
        if not output_path.exists():
            raise InvalidDocumentStructureError("Pages export finished without creating a PDF")
        return output_path

    def _package_strings(self, archive: zipfile.ZipFile, *, include_tables: bool) -> list[str]:
        strings: list[str] = []
        for name in archive.namelist():
            if not name.endswith(".iwa"):
                continue
            if not include_tables and "/Tables/" in name:
                continue
            try:
                strings.extend(self._strings_from_payload(archive.read(name)))
            except Exception:
                logger.debug("Failed to extract strings from %s", name)
        return self._clean_text_values(strings)

    def _strings_from_payload(self, data: bytes) -> list[str]:
        strings: list[str] = []
        for message in _IWAParser(data).parse():
            strings.extend(self._strings_from_message(message))
        return strings

    def _strings_from_message(self, message: bytes) -> list[str]:
        fields = self._decoder.decode(message)
        strings = _collect_strings(fields)
        if strings:
            return strings
        return _extract_printable_runs(message)

    def _split_paragraph_candidates(self, value: str) -> list[str]:
        blocks: list[str] = []
        for block in re.split(r"\n\s*\n", value):
            candidate = " ".join(line.strip() for line in block.splitlines() if line.strip()).strip()
            if candidate:
                blocks.append(candidate)
        return blocks or [value.strip()]

    def _paragraphs_from_text(self, text: str) -> list[Paragraph]:
        if not text.strip():
            return []

        paragraphs: list[Paragraph] = []
        for block in re.split(r"\n\s*\n", text):
            candidate = " ".join(line.strip() for line in block.splitlines() if line.strip()).strip()
            if not candidate:
                continue
            paragraph = self._make_paragraph(candidate)
            if paragraph is not None:
                paragraphs.append(paragraph)
        return self._dedupe_paragraphs(paragraphs)

    def _make_paragraph(self, text: str) -> Paragraph | None:
        candidate = text.strip()
        if not self._should_keep_text(candidate):
            return None

        is_heading = self._looks_like_heading(candidate)
        style = DEFAULT_HEADING_STYLE if is_heading else DEFAULT_PARAGRAPH_STYLE
        return Paragraph(
            runs=[TextRun(text=candidate, style=style)],
            style=style,
            is_heading=is_heading,
            heading_level=1 if is_heading else None,
        )

    def _cells_from_values(self, values: Sequence[str]) -> list[TableCell]:
        cells: list[TableCell] = []
        for value in values:
            paragraph = Paragraph(
                runs=[TextRun(text=value, style=DEFAULT_PARAGRAPH_STYLE)],
                style=DEFAULT_PARAGRAPH_STYLE,
            )
            cells.append(TableCell(paragraphs=[paragraph], style=DEFAULT_PARAGRAPH_STYLE))
        return cells

    def _delimited_rows_from_strings(self, strings: Sequence[str]) -> list[list[str]]:
        rows: list[list[str]] = []
        for value in strings:
            lines = [line.strip() for line in value.splitlines() if line.strip()]
            if not lines:
                continue

            delimiter = self._guess_delimiter(lines)
            if delimiter is None:
                continue

            parsed = [self._split_delimited_line(line, delimiter) for line in lines]
            parsed = [row for row in parsed if len(row) > 1]
            if parsed:
                rows.extend(parsed)
        return rows

    def _guess_delimiter(self, lines: Sequence[str]) -> str | None:
        scores = dict.fromkeys(DELIMITER_CANDIDATES, 0)
        for line in lines[:20]:
            for delimiter in DELIMITER_CANDIDATES:
                count = line.count(delimiter)
                if count > 0:
                    scores[delimiter] += count
        delimiter, score = max(scores.items(), key=lambda item: item[1])
        return delimiter if score > 0 else None

    def _split_delimited_line(self, line: str, delimiter: str) -> list[str]:
        return [part.strip() for part in line.split(delimiter)][:MAX_TABLE_COLUMNS]

    def _extract_title(self, values: Sequence[str]) -> str | None:
        for value in values:
            candidate = value.strip()
            if not self._should_keep_text(candidate):
                continue
            if self._looks_like_heading(candidate):
                return candidate
        return values[0].strip() if values else None

    def _should_use_textutil_fallback(
        self,
        paragraphs: Sequence[Paragraph],
        tables: Sequence[Table],
    ) -> bool:
        if not self.use_textutil_fallback or not self.is_macos:
            return False
        if not paragraphs:
            return True
        if len(paragraphs) == 1 and len(self._paragraph_text(paragraphs[0])) < 20 and not tables:
            return True
        return False

    def _clean_text_values(self, values: Iterable[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            for line in value.splitlines():
                candidate = line.strip().strip("\x00")
                if self._should_keep_text(candidate):
                    cleaned.append(candidate)
        return _dedupe_preserve_order(cleaned)

    def _should_keep_text(self, value: str) -> bool:
        candidate = value.strip()
        if not candidate:
            return False
        if not _is_meaningful_string(candidate):
            return False
        if candidate.lower().startswith(("http://", "https://")) and len(candidate) > 120:
            return False
        if re.fullmatch(r"[A-Fa-f0-9]{24,}", candidate):
            return False
        return True

    def _dedupe_paragraphs(self, paragraphs: Sequence[Paragraph]) -> list[Paragraph]:
        deduped: list[Paragraph] = []
        seen: set[str] = set()
        for paragraph in paragraphs:
            text = self._paragraph_text(paragraph).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            deduped.append(paragraph)
        return deduped

    def _paragraph_text(self, paragraph: Paragraph) -> str:
        return "".join(run.text for run in paragraph.runs)

    def _looks_like_heading(self, value: str) -> bool:
        stripped = value.strip()
        if not stripped:
            return False
        if len(stripped) > 120:
            return False
        if len(stripped.split()) > 14:
            return False
        if stripped.endswith((".jpg", ".png", ".iwa")):
            return False
        return stripped[:1].isupper() and any(char.isalpha() for char in stripped)

    def _flatten_plist(self, value: Any, prefix: str = "") -> dict[str, Any]:
        flattened: dict[str, Any] = {}
        if isinstance(value, dict):
            for key, item in value.items():
                child_prefix = f"{prefix}.{key}" if prefix else str(key)
                flattened.update(self._flatten_plist(item, prefix=child_prefix))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                child_prefix = f"{prefix}[{index}]"
                flattened.update(self._flatten_plist(item, prefix=child_prefix))
        else:
            flattened[prefix or "value"] = value
        return flattened

    def _coerce_datetime(self, value: Any) -> datetime | None:
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return None
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        return None

    def _coerce_scalar(self, value: Any) -> str | int | float | bool | datetime | None:
        if isinstance(value, (str, int, float, bool, datetime)):
            return value
        return None

    def _escape_applescript_string(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _natural_sort_key(self, value: str) -> tuple[Any, ...]:
        parts = re.split(r"(\d+)", value)
        return tuple(int(part) if part.isdigit() else part.lower() for part in parts)


def _read_varint(data: bytes, position: int) -> tuple[int, int]:
    """Read a protobuf varint starting at ``position``."""

    result = 0
    shift = 0

    for _ in range(PROTOBUF_VARINT_MAX):
        if position >= len(data):
            raise ValueError("Unexpected end of varint")
        byte = data[position]
        position += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, position
        shift += 7

    raise ValueError("Invalid varint")


def _pick_numeric_value(int_value: int, float_value: float) -> int | float:
    """Choose the more human-useful view of a numeric protobuf field."""

    if math.isfinite(float_value) and not math.isnan(float_value):
        if abs(float_value) > 0 and abs(float_value) < 1e12 and not float_value.is_integer():
            return float_value
    return int_value


def _strip_possible_iwa_header(data: bytes) -> bytes:
    """Strip small wrapper headers occasionally found in IWA chunks."""

    if len(data) > 8 and data[:4] == IWA_MAGIC:
        return data[4:]
    return data


def _looks_like_nested_protobuf(data: bytes) -> bool:
    """Heuristic check for nested protobuf content."""

    if len(data) < 2:
        return False
    if any(byte == 0 for byte in data[:8]):
        return False
    first = data[0]
    return 0 < first < 0x80


def _try_decode_text(data: bytes) -> str | None:
    """Decode a candidate UTF-8 payload if it looks meaningful."""

    if not data or len(data) > MAX_TEXT_LENGTH:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None
    cleaned = text.strip("\x00\r\n\t ")
    return cleaned if _is_meaningful_string(cleaned) else None


def _collect_strings(fields: Sequence[_ProtoField]) -> list[str]:
    """Collect decoded strings from a protobuf field tree."""

    values: list[str] = []
    for proto_field in fields:
        value = proto_field.value
        if isinstance(value, _DecodedBytes):
            if value.text:
                values.append(value.text)
            if value.message:
                values.extend(_collect_strings(value.message))
    return values


def _extract_printable_runs(data: bytes) -> list[str]:
    """Fallback printable-string extraction from raw bytes."""

    values: list[str] = []
    for match in PRINTABLE_RUN_RE.findall(data):
        try:
            value = match.decode("utf-8").strip()
        except UnicodeDecodeError:
            continue
        if _is_meaningful_string(value):
            values.append(value)
    return _dedupe_preserve_order(values)


def _is_meaningful_string(text: str) -> bool:
    """Return whether a decoded string is likely user-visible content."""

    if not text:
        return False
    cleaned = text.strip()
    if len(cleaned) < 1 or len(cleaned) > 512:
        return False
    if cleaned in SYSTEMISH_STRINGS:
        return False
    if cleaned.startswith(NOISE_PREFIXES):
        return False
    if cleaned.endswith(".iwa"):
        return False
    if cleaned.startswith("/") or cleaned.startswith("file://"):
        return False

    normalized = cleaned.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    printable_ratio = sum(char.isprintable() or char.isspace() for char in normalized) / len(
        normalized
    )
    if printable_ratio < 0.9:
        return False

    if any(char.isalpha() for char in cleaned):
        return True

    if cleaned.lower() in {"true", "false", "yes", "no"}:
        return True

    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?%?", cleaned)) and not DATE_RE.match(cleaned)


def _extract_authorish_string(values: Sequence[str]) -> str | None:
    """Return the first string that looks like an author identity."""

    for value in values:
        if "@" in value and len(value) <= 128:
            return value
    return None


def _extract_pages_app_version(values: Sequence[str]) -> str | None:
    """Infer a Pages version string from package text."""

    for value in values:
        lowered = value.lower()
        if "pages" in lowered and any(char.isdigit() for char in value):
            return value
    return None


def _dedupe_preserve_order(values: Iterable[Any]) -> list[Any]:
    """Deduplicate while preserving order."""

    seen: set[Any] = set()
    deduped: list[Any] = []
    for value in values:
        key = value if isinstance(value, (str, int, float, bool, tuple)) else repr(value)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(value)
    return deduped


def extract_text(path: Path | str) -> str:
    """Convenience helper returning plain text from a Pages document."""

    return PagesProcessor().extract_text(path)


def convert_to_pdf(input_path: Path | str, output_path: Path | str) -> Path:
    """Convenience helper exporting a Pages document to PDF."""

    return PagesProcessor().to_pdf(input_path, output_path)
