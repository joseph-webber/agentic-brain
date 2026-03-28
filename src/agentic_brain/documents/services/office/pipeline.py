"""
Unified Office document processing pipeline.

This module provides a single entry-point that can ingest any supported Office,
iWork, OpenDocument, or legacy RTF document and run a standardized set of
operations:

* Detect the document format using both file extensions and magic bytes.
* Route to the appropriate processor (Word, Excel, PowerPoint, Pages, Numbers,
  Keynote, OpenDocument, RTF).
* Extract rich document content, flattened text, tables, and image metadata.
* Apply Phase 2 security scanning (PII detection, macro scan, external links)
  when the format is compatible.
* Generate a Phase 3 accessibility report when OOXML dependencies are
  available.
* Support batch processing with aggregated error reporting.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import logging
from pathlib import Path
from typing import Any, Iterable, Sequence
import zipfile

from .accessibility import AccessibilityReport, OfficeAccessibilityProcessor
from .exceptions import UnsupportedOfficeFormatError
from .models import Table, TableCell, Paragraph, Image, Slide, Worksheet, Chart, OfficeFormat
from .word import WordProcessor
from .excel import ExcelProcessor
from .powerpoint import PowerPointProcessor
from .apple_pages import PagesProcessor
from .apple_numbers import NumbersProcessor
from .apple_keynote import KeynoteProcessor
from .opendocument import OpenDocumentProcessor
from .rtf import RTFProcessor
from .security import (
    OfficeSecurityService,
    OfficePIIMatch,
    MacroCheckResult,
    ExternalLinkReport,
)

logger = logging.getLogger(__name__)

MAGIC_RTF = b"{\\rtf"
MAGIC_ZIP = b"PK\x03\x04"


@dataclass(slots=True)
class SecurityScanResult:
    """Envelope for Phase 2 security artifacts."""

    pii_matches: list[OfficePIIMatch] = field(default_factory=list)
    macro_report: MacroCheckResult | None = None
    external_links: ExternalLinkReport | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class PipelineError:
    """Represents a failure while processing a specific file."""

    path: Path
    message: str
    exception: Exception | None = None


@dataclass(slots=True)
class OfficeDocumentResult:
    """Successful processing artifact."""

    path: Path
    format: OfficeFormat
    processor: str
    content: Any
    text: str
    tables: list[Any]
    images: list[Any]
    metadata: Any | None
    security: SecurityScanResult | None = None
    accessibility: AccessibilityReport | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class BatchProcessingResult:
    """Result of processing multiple files."""

    results: list[OfficeDocumentResult] = field(default_factory=list)
    errors: list[PipelineError] = field(default_factory=list)


class OfficeDocumentPipeline:
    """High-level orchestrator for Office document ingestion."""

    _EXTENSION_MAP: dict[str, OfficeFormat] = {
        "docx": OfficeFormat.DOCX,
        "doc": OfficeFormat.DOCX,
        "dotx": OfficeFormat.DOCX,
        "dotm": OfficeFormat.DOCX,
        "rtf": OfficeFormat.RTF,
        "xlsx": OfficeFormat.XLSX,
        "xls": OfficeFormat.XLSX,
        "xlsm": OfficeFormat.XLSX,
        "xltx": OfficeFormat.XLSX,
        "xltm": OfficeFormat.XLSX,
        "pptx": OfficeFormat.PPTX,
        "ppt": OfficeFormat.PPTX,
        "pptm": OfficeFormat.PPTX,
        "odt": OfficeFormat.ODT,
        "ods": OfficeFormat.ODS,
        "odp": OfficeFormat.ODP,
        "pages": OfficeFormat.PAGES,
        "numbers": OfficeFormat.NUMBERS,
        "key": OfficeFormat.KEYNOTE,
        "keynote": OfficeFormat.KEYNOTE,
    }

    _ODF_MIME_MAP: dict[str, OfficeFormat] = {
        "application/vnd.oasis.opendocument.text": OfficeFormat.ODT,
        "application/vnd.oasis.opendocument.spreadsheet": OfficeFormat.ODS,
        "application/vnd.oasis.opendocument.presentation": OfficeFormat.ODP,
    }

    _SECURITY_FORMATS = {OfficeFormat.DOCX, OfficeFormat.XLSX, OfficeFormat.PPTX}
    _ACCESSIBILITY_FORMATS = {OfficeFormat.DOCX, OfficeFormat.XLSX, OfficeFormat.PPTX}

    def __init__(
        self,
        *,
        security_service: OfficeSecurityService | None = None,
        accessibility_processor: OfficeAccessibilityProcessor | None = None,
        enable_security: bool = True,
        enable_accessibility: bool = True,
    ) -> None:
        self.security_service = security_service if enable_security else None
        self.accessibility_processor = (
            accessibility_processor if enable_accessibility else None
        )
        self._processors: dict[OfficeFormat, Any] = {}
        self._processor_factories: dict[OfficeFormat, type] = {
            OfficeFormat.DOCX: WordProcessor,
            OfficeFormat.XLSX: ExcelProcessor,
            OfficeFormat.PPTX: PowerPointProcessor,
            OfficeFormat.PAGES: PagesProcessor,
            OfficeFormat.NUMBERS: NumbersProcessor,
            OfficeFormat.KEYNOTE: KeynoteProcessor,
            OfficeFormat.ODT: OpenDocumentProcessor,
            OfficeFormat.ODS: OpenDocumentProcessor,
            OfficeFormat.ODP: OpenDocumentProcessor,
            OfficeFormat.RTF: RTFProcessor,
        }

    # ------------------------------------------------------------------ Public API
    def process(self, file_path: str | Path) -> OfficeDocumentResult:
        """Process a single document path."""

        path = Path(file_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"Office pipeline input not found: {path}")
        if not path.is_file():
            raise FileNotFoundError(f"Office pipeline requires a file, got: {path}")

        office_format = self._detect_format(path)
        processor = self.get_processor(office_format)
        processor_name = type(processor).__name__

        logger.debug("Processing %s as %s via %s", path.name, office_format, processor_name)

        content = processor.parse(path)
        text = self._render_text(content)
        tables = list(getattr(content, "tables", []) or [])
        images = list(getattr(content, "images", []) or [])
        metadata = getattr(content, "metadata", None)

        warnings: list[str] = []
        security_result = self._maybe_run_security(path, office_format, warnings)
        accessibility_report = self._maybe_run_accessibility(path, office_format, warnings)

        return OfficeDocumentResult(
            path=path,
            format=office_format,
            processor=processor_name,
            content=content,
            text=text,
            tables=tables,
            images=images,
            metadata=metadata,
            security=security_result,
            accessibility=accessibility_report,
            warnings=warnings,
        )

    def process_batch(self, paths: Iterable[str | Path]) -> BatchProcessingResult:
        """Process multiple documents, capturing per-file errors."""

        results: list[OfficeDocumentResult] = []
        errors: list[PipelineError] = []

        for candidate in paths:
            try:
                results.append(self.process(candidate))
            except Exception as exc:  # pragma: no cover - defensive aggregation
                resolved = Path(candidate).expanduser()
                message = str(exc)
                logger.exception("Pipeline failed for %s: %s", resolved, exc)
                errors.append(PipelineError(path=resolved, message=message, exception=exc))

        return BatchProcessingResult(results=results, errors=errors)

    def get_processor(self, office_format: OfficeFormat) -> Any:
        """Return (and cache) the processor for the requested format."""

        if office_format in self._processors:
            return self._processors[office_format]

        factory = self._processor_factories.get(office_format)
        if factory is None:
            raise UnsupportedOfficeFormatError(office_format)

        try:
            processor = factory()
        except Exception as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                f"Failed to initialize processor for {office_format.value}: {exc}"
            ) from exc

        self._processors[office_format] = processor
        return processor

    # ------------------------------------------------------------------ Detection
    def _detect_format(self, path: Path) -> OfficeFormat:
        extension = path.suffix.lower().lstrip(".")
        if extension in self._EXTENSION_MAP:
            return self._EXTENSION_MAP[extension]

        header = self._read_magic(path, 8)
        if header.startswith(MAGIC_RTF):
            return OfficeFormat.RTF
        if header.startswith(MAGIC_ZIP):
            detected = self._detect_zip_format(path)
            if detected is not None:
                return detected

        raise UnsupportedOfficeFormatError(extension or path.suffix or path.name)

    def _detect_zip_format(self, path: Path) -> OfficeFormat | None:
        try:
            with zipfile.ZipFile(path, "r") as archive:
                names = set(archive.namelist())
                if "word/document.xml" in names:
                    return OfficeFormat.DOCX
                if "xl/workbook.xml" in names or "xl/sharedStrings.xml" in names:
                    return OfficeFormat.XLSX
                if "ppt/presentation.xml" in names or "ppt/slides/slide1.xml" in names:
                    return OfficeFormat.PPTX
                if "mimetype" in names:
                    try:
                        mimetype = archive.read("mimetype").decode("utf-8", errors="ignore").strip()
                    except Exception:
                        mimetype = ""
                    detected = self._ODF_MIME_MAP.get(mimetype.lower())
                    if detected:
                        return detected
                if any(name.startswith("Index/Document.iwa") for name in names):
                    if any("Slide" in name or "Animation" in name for name in names):
                        return OfficeFormat.KEYNOTE
                    if any("Tables" in name or "Table" in name for name in names):
                        return OfficeFormat.NUMBERS
                    return OfficeFormat.PAGES
        except zipfile.BadZipFile:
            return None
        return None

    @staticmethod
    def _read_magic(path: Path, length: int) -> bytes:
        with path.open("rb") as handle:
            return handle.read(length)

    # ------------------------------------------------------------------ Security / Accessibility
    def _maybe_run_security(
        self,
        path: Path,
        office_format: OfficeFormat,
        warnings: list[str],
    ) -> SecurityScanResult | None:
        if self.security_service is None:
            return None
        if office_format not in self._SECURITY_FORMATS:
            warnings.append(f"Security scanning skipped for {office_format.value.upper()}.")
            return None

        result = SecurityScanResult()
        try:
            result.pii_matches = self.security_service.scan_for_pii(path)
        except Exception as exc:  # pragma: no cover - defensive
            warning = f"PII scan failed: {exc}"
            warnings.append(warning)
            result.warnings.append(warning)

        try:
            result.macro_report = self.security_service.check_macros(path)
        except Exception as exc:  # pragma: no cover - defensive
            warning = f"Macro scan failed: {exc}"
            warnings.append(warning)
            result.warnings.append(warning)

        try:
            result.external_links = self.security_service.check_external_links(path)
        except Exception as exc:  # pragma: no cover - defensive
            warning = f"External link scan failed: {exc}"
            warnings.append(warning)
            result.warnings.append(warning)

        return result

    def _maybe_run_accessibility(
        self,
        path: Path,
        office_format: OfficeFormat,
        warnings: list[str],
    ) -> AccessibilityReport | None:
        if self.accessibility_processor is None:
            return None
        if office_format not in self._ACCESSIBILITY_FORMATS:
            warnings.append(f"Accessibility report skipped for {office_format.value.upper()}.")
            return None

        try:
            return self.accessibility_processor.generate_accessibility_report(path)
        except Exception as exc:  # pragma: no cover - best-effort
            warning = f"Accessibility analysis failed: {exc}"
            warnings.append(warning)
            return None

    # ------------------------------------------------------------------ Text rendering helpers
    def _render_text(self, content: Any) -> str:
        blocks: list[str] = []

        explicit_text = getattr(content, "text", None)
        if isinstance(explicit_text, str) and explicit_text.strip():
            blocks.append(explicit_text.strip())

        paragraphs = getattr(content, "paragraphs", None)
        if paragraphs:
            for paragraph in paragraphs:
                text = self._paragraph_text(paragraph)
                if text:
                    blocks.append(text)

        tables = getattr(content, "tables", None)
        if tables:
            for table in tables:
                rendered = self._table_text(table)
                if rendered:
                    blocks.append(rendered)

        slides = getattr(content, "slides", None)
        if slides:
            for index, slide in enumerate(slides, start=1):
                rendered = self._slide_text(slide, index)
                if rendered:
                    blocks.append(rendered)

        worksheets = getattr(content, "worksheets", None) or getattr(content, "sheets", None)
        if worksheets:
            for worksheet in worksheets:
                rendered = self._worksheet_text(worksheet)
                if rendered:
                    blocks.append(rendered)

        charts = getattr(content, "charts", None)
        if charts:
            for chart in charts:
                title = getattr(chart, "title", None)
                chart_type = getattr(chart, "chart_type", "chart")
                if title:
                    blocks.append(f"{chart_type.capitalize()} chart: {title}")

        if not blocks:
            resources = getattr(content, "resources", None) or {}
            if isinstance(resources, dict):
                for key in resources.keys():
                    blocks.append(f"[embedded resource: {key}]")

        return "\n\n".join(blocks).strip()

    @staticmethod
    def _paragraph_text(paragraph: Any) -> str:
        if paragraph is None:
            return ""
        if hasattr(paragraph, "text_content"):
            return str(paragraph.text_content()).strip()
        if hasattr(paragraph, "text"):
            return str(getattr(paragraph, "text")).strip()
        runs = getattr(paragraph, "runs", None)
        if runs:
            return "".join(str(getattr(run, "text", "")) for run in runs).strip()
        return str(paragraph).strip()

    def _table_text(self, table: Any, max_rows: int = 25) -> str:
        rows = getattr(table, "rows", None)
        if not rows:
            return ""
        lines = ["Table:"]
        for row_index, row in enumerate(rows, start=1):
            if row_index > max_rows:
                lines.append(f"... ({len(rows) - max_rows} more rows)")
                break
            cells = []
            for cell in row:
                if isinstance(cell, TableCell):
                    cells.append(cell.text_content().strip())
                elif hasattr(cell, "text_content"):
                    cells.append(str(cell.text_content()).strip())
                elif hasattr(cell, "text"):
                    cells.append(str(cell.text).strip())
                else:
                    cells.append(str(cell).strip())
            lines.append(" | ".join(filter(None, cells)))
        return "\n".join(filter(None, lines))

    def _slide_text(self, slide: Any, index: int) -> str:
        title_paragraph = getattr(slide, "title", None)
        body = getattr(slide, "body", None) or getattr(slide, "content", None) or []
        notes = getattr(slide, "notes", None) or []

        lines = [f"Slide {index}: {self._paragraph_text(title_paragraph) or 'Untitled'}"]

        for paragraph in body:
            text = self._paragraph_text(paragraph)
            if text:
                lines.append(f"- {text}")

        if notes:
            lines.append("Speaker notes:")
            for note in notes:
                text = self._paragraph_text(note)
                if text:
                    lines.append(f"  • {text}")

        return "\n".join(lines).strip()

    def _worksheet_text(self, worksheet: Any, max_rows: int = 50) -> str:
        name = getattr(worksheet, "name", None) or getattr(worksheet, "title", None) or "Sheet"
        lines = [f"Worksheet: {name}"]

        cells = getattr(worksheet, "cells", None)
        entries: list[Any] = []
        if isinstance(cells, dict):
            entries.extend(cells.values())
        elif isinstance(cells, list):
            entries.extend(cells)

        if not entries and hasattr(worksheet, "rows"):
            entries.extend(getattr(worksheet, "rows"))

        if not entries:
            return ""

        grid: dict[int, dict[int, str]] = defaultdict(dict)
        for cell in entries:
            row, column = self._cell_position(cell)
            if row is None or column is None:
                continue
            value = getattr(cell, "display_value", None)
            if value is None:
                value = getattr(cell, "value", None)
            if value is None and hasattr(cell, "text_content"):
                value = cell.text_content()
            grid[row][column] = str(value) if value is not None else ""

        for row_index in sorted(grid)[:max_rows]:
            row_cells = grid[row_index]
            ordered = [row_cells[column] for column in sorted(row_cells)]
            lines.append(f"R{row_index}: {' | '.join(ordered)}")

        row_count = len(grid)
        if row_count > max_rows:
            lines.append(f"... ({row_count - max_rows} more rows)")

        return "\n".join(lines).strip()

    @staticmethod
    def _cell_position(cell: Any) -> tuple[int | None, int | None]:
        if hasattr(cell, "row") and hasattr(cell, "column"):
            return getattr(cell, "row"), getattr(cell, "column")
        reference = getattr(cell, "reference", None)
        if isinstance(reference, str):
            column_part = "".join(ch for ch in reference if ch.isalpha())
            row_part = "".join(ch for ch in reference if ch.isdigit())
            if column_part and row_part:
                return int(row_part), OfficeDocumentPipeline._column_index(column_part)
        coordinate = getattr(cell, "coordinate", None)
        if isinstance(coordinate, str):
            column_part = "".join(ch for ch in coordinate if ch.isalpha())
            row_part = "".join(ch for ch in coordinate if ch.isdigit())
            if column_part and row_part:
                return int(row_part), OfficeDocumentPipeline._column_index(column_part)
        return None, None

    @staticmethod
    def _column_index(column: str) -> int:
        total = 0
        for char in column.upper():
            if not char.isalpha():
                continue
            total = total * 26 + (ord(char) - ord("A") + 1)
        return total


__all__ = [
    "OfficeDocumentPipeline",
    "OfficeDocumentResult",
    "BatchProcessingResult",
    "SecurityScanResult",
    "PipelineError",
]
