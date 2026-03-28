"""Public convenience API for office document workflows.

This module wraps the lower-level processors that live in
``agentic_brain.documents.services.office`` and exposes an intuitive
function-based surface for common tasks such as text extraction, table/image
harvesting, format conversion, PII scanning, and RAG ingestion.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Dict, Iterable, Optional

from ...rag.store import Document as RagDocument, InMemoryDocumentStore
from ..accessibility.api import make_accessible, validate_accessibility
from ..accessibility.models import AccessibilityReport, RemediationResult
from .converter import ConversionError, OfficeConverter
from .images import Image as ExtractedImage, ImageExtractor
from .security import OfficePIIMatch, OfficeSecurityService
from .tables import Table as NormalizedTable, TableExtractor

FormatParser = Callable[[Path], tuple[Any, str, dict[str, Any]]]

_TABLE_EXTRACTOR: TableExtractor | None = None
_IMAGE_EXTRACTOR: ImageExtractor | None = None
_SECURITY_SERVICE: OfficeSecurityService | None = None
_CONVERTER: OfficeConverter | None = None


@dataclass(slots=True)
class DocumentContent:
    """High-level summary of an office document."""

    path: Path
    format: str
    text: str
    tables: list[NormalizedTable]
    images: list[ExtractedImage]
    metadata: dict[str, Any]
    raw: Any | None = None

    def summary(self) -> dict[str, Any]:
        """Return a lightweight serializable summary."""

        return {
            "path": str(self.path),
            "format": self.format,
            "text_preview": self.text[:2000],
            "table_count": len(self.tables),
            "image_count": len(self.images),
            "metadata": self.metadata,
        }


# --------------------------------------------------------------------------- #
# Core helpers
# --------------------------------------------------------------------------- #


def _resolve_path(path: Path | str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"File not found: {resolved}")
    if not resolved.is_file():
        raise ValueError(f"Expected a file, got: {resolved}")
    return resolved


def _detect_format(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"docm", "dotx"}:
        return "docx"
    if suffix in {"xlsm", "xlsb"}:
        return "xlsx"
    if suffix in {"pptm", "potx"}:
        return "pptx"
    if suffix in {"key"}:
        return "keynote"
    return suffix or ""


def _get_table_extractor() -> TableExtractor:
    global _TABLE_EXTRACTOR
    if _TABLE_EXTRACTOR is None:
        _TABLE_EXTRACTOR = TableExtractor()
    return _TABLE_EXTRACTOR


def _get_image_extractor() -> ImageExtractor:
    global _IMAGE_EXTRACTOR
    if _IMAGE_EXTRACTOR is None:
        _IMAGE_EXTRACTOR = ImageExtractor()
    return _IMAGE_EXTRACTOR


def _get_security_service() -> OfficeSecurityService:
    global _SECURITY_SERVICE
    if _SECURITY_SERVICE is None:
        _SECURITY_SERVICE = OfficeSecurityService()
    return _SECURITY_SERVICE


def _get_converter() -> OfficeConverter:
    global _CONVERTER
    if _CONVERTER is None:
        _CONVERTER = OfficeConverter()
    return _CONVERTER


def _metadata_from_obj(candidate: Any) -> dict[str, Any]:
    if candidate is None:
        return {}
    if is_dataclass(candidate):
        return asdict(candidate)
    if isinstance(candidate, dict):
        return dict(candidate)
    return {"value": str(candidate)}


def _parse_docx(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .word import WordProcessor

    processor = WordProcessor()
    raw = processor.parse(path)
    text = processor.extract_text()
    metadata = {}
    content_meta = getattr(raw, "metadata", None)
    if content_meta:
        metadata = _metadata_from_obj(content_meta)
    return raw, text, metadata


def _parse_rtf(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .rtf import RTFProcessor

    processor = RTFProcessor()
    raw = processor.parse(path)
    text = processor.extract_text()
    metadata = _metadata_from_obj(getattr(raw, "metadata", None))
    return raw, text, metadata


def _parse_xlsx(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .excel import ExcelProcessor

    processor = ExcelProcessor(read_only=True, data_only=True)
    raw = processor.parse(path)
    text_lines: list[str] = []
    for sheet in getattr(raw, "worksheets", []):
        text_lines.append(f"# Worksheet: {sheet.name}")
        for ref in sorted(sheet.cells):
            value = sheet.cells[ref].value
            if value in (None, ""):
                continue
            text_lines.append(f"{ref}: {value}")
        text_lines.append("")
    text = "\n".join(text_lines).strip()
    metadata = _metadata_from_obj(getattr(raw, "metadata", None))
    return raw, text, metadata


def _parse_pptx(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .powerpoint import PowerPointProcessor

    processor = PowerPointProcessor(path)
    raw = processor.parse()
    text = processor.extract_text()
    metadata = _metadata_from_obj(getattr(raw, "metadata", None))
    return raw, text, metadata


def _parse_pages(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .apple_pages import PagesProcessor

    processor = PagesProcessor()
    raw = processor.parse(path)
    text = raw.text if hasattr(raw, "text") else processor.extract_text(path)
    metadata = _metadata_from_obj(getattr(raw, "metadata", None))
    return raw, text, metadata


def _parse_numbers(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .apple_numbers import NumbersProcessor

    processor = NumbersProcessor()
    raw = processor.parse(path)
    text_lines = []
    for sheet in raw.sheets:
        text_lines.append(f"# Sheet: {sheet.name}")
        for cell in sorted(raw.cells, key=lambda c: (c.sheet_name, c.row, c.column)):
            if cell.sheet_name != sheet.name:
                continue
            if cell.display_value:
                text_lines.append(f"R{cell.row}C{cell.column}: {cell.display_value}")
        text_lines.append("")
    text = "\n".join(text_lines).strip()
    metadata = _metadata_from_obj(raw.metadata)
    return raw, text, metadata


def _parse_keynote(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .apple_keynote import KeynoteProcessor

    processor = KeynoteProcessor()
    raw = processor.parse(path)
    text = processor.extract_text()
    metadata = _metadata_from_obj(getattr(raw, "metadata", None))
    return raw, text, metadata


def _parse_odf(path: Path) -> tuple[Any, str, dict[str, Any]]:
    from .opendocument import OpenDocumentProcessor

    processor = OpenDocumentProcessor()
    raw = processor.parse(path)
    text = raw.text
    metadata = _metadata_from_obj(getattr(raw, "metadata", None))
    return raw, text, metadata


_FORMAT_PARSERS: dict[str, FormatParser] = {
    "docx": _parse_docx,
    "rtf": _parse_rtf,
    "xlsx": _parse_xlsx,
    "pptx": _parse_pptx,
    "pages": _parse_pages,
    "numbers": _parse_numbers,
    "keynote": _parse_keynote,
    "key": _parse_keynote,
    "odt": _parse_odf,
    "ods": _parse_odf,
    "odp": _parse_odf,
}


def _parse_document(path: Path, fmt: str) -> tuple[Any, str, dict[str, Any]]:
    parser = _FORMAT_PARSERS.get(fmt)
    if not parser:
        raise ValueError(f"Unsupported office format: {fmt}")
    return parser(path)


def _safe_extract_tables(path: Path) -> list[NormalizedTable]:
    try:
        return _get_table_extractor().extract_tables(path)
    except Exception:
        return []


def _safe_extract_images(path: Path) -> list[ExtractedImage]:
    try:
        return _get_image_extractor().extract_images(path)
    except Exception:
        return []


def _ensure_pdf(path: Path | str) -> tuple[Path, Path | None]:
    resolved = _resolve_path(path)
    if resolved.suffix.lower() == ".pdf":
        return resolved, None
    with NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
        temp_path = Path(handle.name)
    convert_to_pdf(resolved, temp_path)
    return temp_path, temp_path


# --------------------------------------------------------------------------- #
# Quick processing helpers
# --------------------------------------------------------------------------- #


def process_office_document(path: Path | str) -> DocumentContent:
    resolved = _resolve_path(path)
    fmt = _detect_format(resolved)
    raw, text, metadata = _parse_document(resolved, fmt)
    tables = _safe_extract_tables(resolved)
    images = _safe_extract_images(resolved)
    return DocumentContent(
        path=resolved,
        format=fmt,
        text=text,
        tables=tables,
        images=images,
        metadata=metadata,
        raw=raw,
    )


def extract_text(path: Path | str) -> str:
    resolved = _resolve_path(path)
    _, text, _ = _parse_document(resolved, _detect_format(resolved))
    return text


def extract_tables(path: Path | str) -> list[NormalizedTable]:
    return _safe_extract_tables(_resolve_path(path))


def extract_images(path: Path | str, output_dir: Path | str | None = None) -> list[ExtractedImage]:
    images = _safe_extract_images(_resolve_path(path))
    if output_dir:
        target_dir = Path(output_dir).expanduser()
        target_dir.mkdir(parents=True, exist_ok=True)
        for index, image in enumerate(images, start=1):
            suffix = image.get_format()
            filename = f"image_{index}.{suffix}"
            image.save(target_dir / filename)
    return images


# --------------------------------------------------------------------------- #
# Format-specific helpers
# --------------------------------------------------------------------------- #


def process_word(path: Path | str) -> DocumentContent:
    resolved = _resolve_path(path)
    if _detect_format(resolved) != "docx":
        raise ValueError("process_word expects a .docx file")
    return process_office_document(resolved)


def process_excel(path: Path | str) -> DocumentContent:
    resolved = _resolve_path(path)
    if _detect_format(resolved) != "xlsx":
        raise ValueError("process_excel expects an .xlsx file")
    return process_office_document(resolved)


def process_powerpoint(path: Path | str) -> DocumentContent:
    resolved = _resolve_path(path)
    if _detect_format(resolved) != "pptx":
        raise ValueError("process_powerpoint expects a .pptx file")
    return process_office_document(resolved)


def process_pages(path: Path | str) -> DocumentContent:
    resolved = _resolve_path(path)
    if _detect_format(resolved) != "pages":
        raise ValueError("process_pages expects a .pages file")
    return process_office_document(resolved)


def process_numbers(path: Path | str) -> DocumentContent:
    resolved = _resolve_path(path)
    if _detect_format(resolved) != "numbers":
        raise ValueError("process_numbers expects a .numbers file")
    return process_office_document(resolved)


def process_keynote(path: Path | str) -> DocumentContent:
    resolved = _resolve_path(path)
    if _detect_format(resolved) not in {"keynote", "key"}:
        raise ValueError("process_keynote expects a .key or .keynote file")
    return process_office_document(resolved)


# --------------------------------------------------------------------------- #
# Conversion helpers
# --------------------------------------------------------------------------- #


def convert_to_pdf(path: Path | str, output_path: Path | str | None = None) -> Path:
    resolved = _resolve_path(path)
    destination = Path(output_path).expanduser() if output_path else resolved.with_suffix(".pdf")
    destination.parent.mkdir(parents=True, exist_ok=True)
    return _get_converter().to_pdf(resolved, destination)


def convert_to_text(path: Path | str) -> str:
    return extract_text(path)


def convert_format(
    path: Path | str,
    target_format: str,
    output_path: Path | str | None = None,
) -> Path:
    resolved = _resolve_path(path)
    target_format = target_format.lstrip(".").lower()
    destination = (
        Path(output_path).expanduser()
        if output_path
        else resolved.with_suffix(f".{target_format}")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    converter = _get_converter()
    result = converter._convert_with_libreoffice(resolved, destination, target_format)
    return result


# --------------------------------------------------------------------------- #
# Security helpers
# --------------------------------------------------------------------------- #


def scan_for_pii(
    path: Path | str,
    pii_types: Iterable[str] | None = None,
) -> list[OfficePIIMatch]:
    return _get_security_service().scan_for_pii(path, pii_types)


def redact_document(
    path: Path | str,
    output_path: Path | str | None = None,
    pii_types: Iterable[str] | None = None,
) -> Path:
    report = _get_security_service().redact_document(path, output_path, pii_types)
    return Path(report["output_path"])


def scrub_metadata(path: Path | str, output_path: Path | str | None = None) -> Path:
    report = _get_security_service().sanitize_metadata(path, output_path)
    return report.output_path


# --------------------------------------------------------------------------- #
# Accessibility helpers
# --------------------------------------------------------------------------- #


def check_accessibility(path: Path | str) -> AccessibilityReport:
    pdf_path, temp = _ensure_pdf(path)
    try:
        return validate_accessibility(pdf_path)
    finally:
        if temp and temp.exists():
            temp.unlink()


def remediate_accessibility(path: Path | str, output_path: Path | str | None = None) -> RemediationResult:
    pdf_path, temp = _ensure_pdf(path)
    target = Path(output_path) if output_path else pdf_path.with_name(f"{pdf_path.stem}.accessible.pdf")
    try:
        return make_accessible(pdf_path, target)
    finally:
        if temp and temp.exists():
            temp.unlink()


# --------------------------------------------------------------------------- #
# Retrieval-augmented generation helpers
# --------------------------------------------------------------------------- #


def load_for_rag(path: Path | str, chunk_size: int = 512) -> list[RagDocument]:
    document = process_office_document(path)
    store = InMemoryDocumentStore(chunk_size=chunk_size)
    added = store.add(
        content=document.text,
        metadata={
            "source_path": str(document.path),
            "format": document.format,
            "table_count": len(document.tables),
            "image_count": len(document.images),
        },
    )
    return [added]


# --------------------------------------------------------------------------- #
# Batch helpers
# --------------------------------------------------------------------------- #


def process_directory(path: Path | str, recursive: bool = True) -> dict[str, DocumentContent]:
    root = _resolve_path(path)
    results: dict[str, DocumentContent] = {}
    candidates = root.rglob("*") if recursive else root.glob("*")
    for candidate in candidates:
        if not candidate.is_file():
            continue
        fmt = _detect_format(candidate)
        if fmt not in _FORMAT_PARSERS:
            continue
        try:
            results[str(candidate)] = process_office_document(candidate)
        except Exception:
            continue
    return results


__all__ = [
    "DocumentContent",
    "convert_format",
    "convert_to_pdf",
    "convert_to_text",
    "extract_images",
    "extract_tables",
    "extract_text",
    "load_for_rag",
    "process_directory",
    "process_excel",
    "process_keynote",
    "process_numbers",
    "process_office_document",
    "process_pages",
    "process_powerpoint",
    "process_word",
    "redact_document",
    "remediate_accessibility",
    "scan_for_pii",
    "scrub_metadata",
    "check_accessibility",
]
