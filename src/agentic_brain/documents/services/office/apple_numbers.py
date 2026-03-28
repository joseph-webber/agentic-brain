# SPDX-License-Identifier: Apache-2.0

"""Apple Numbers spreadsheet processor for agentic-brain.

Provides best-effort parsing support for Apple Numbers ``.numbers`` packages.
Numbers documents are ZIP archives that typically contain:

- ``Index/Document.iwa`` for workbook structure
- ``Index/Tables/Tile-*.iwa`` for table and cell tile payloads
- ``Data/`` for embedded assets such as images and chart resources
- ``preview.jpg`` for a workbook preview thumbnail

The iWork Archive (IWA) format is proprietary and schema-less from the point of
view of this project, so this implementation focuses on pragmatic extraction:

- ZIP inspection with ``zipfile``
- Snappy decompression when available
- Generic protobuf wire-format walking
- Heuristic extraction of sheets, tables, cells, formulas, and charts
- macOS ``textutil`` fallback when native parsing is insufficient

This is intended for read/extraction workflows rather than lossless round-trip
editing.
"""

from __future__ import annotations

import csv
import logging
import math
import platform
import plistlib
import re
import shutil
import struct
import subprocess
import tempfile
import warnings
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    pd = None
    PANDAS_AVAILABLE = False

try:
    import snappy

    SNAPPY_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    snappy = None
    SNAPPY_AVAILABLE = False

logger = logging.getLogger(__name__)

PROTOBUF_VARINT_MAX = 10
SNAPPY_STREAM_IDENTIFIER = b"\xff\x06\x00\x00sNaPpY"
DEFAULT_SHEET_NAME = "Sheet 1"
MAX_PROTO_RECURSION = 5
MAX_TABLE_COLUMNS = 24
TEXTUTIL_TIMEOUT = 30

FORMULA_RE = re.compile(
    r"^(?:=|SUM\(|AVERAGE\(|COUNT\(|COUNTA\(|MIN\(|MAX\(|IF\(|VLOOKUP\(|XLOOKUP\()",
    re.IGNORECASE,
)
HEX_COLOR_RE = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{8})")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?$")
CHART_TYPE_RE = re.compile(
    r"\b(bar|line|pie|area|scatter|column|donut|bubble|stacked|radar)\b",
    re.IGNORECASE,
)
ALIGNMENT_KEYWORDS = {"left", "center", "right", "justify"}
BOOL_STRINGS = {"true", "false", "yes", "no"}
SYSTEMISH_STRINGS = {
    "Numbers",
    "Document",
    "Document.iwa",
    "Tile",
    "TableModel",
    "DataStore",
    "Index",
    "Data",
}


class NumbersError(Exception):
    """Base exception for Numbers processing errors."""


class NumbersNotFoundError(NumbersError):
    """Raised when the Numbers file does not exist."""


class NumbersCorruptedError(NumbersError):
    """Raised when the Numbers package is invalid or unreadable."""


class NumbersUnsupportedError(NumbersError):
    """Raised when a requested Numbers feature is unsupported."""


@dataclass(slots=True)
class Cell:
    """Single extracted spreadsheet cell."""

    sheet_name: str
    table_name: str
    row: int
    column: int
    value: Any = None
    display_value: str = ""
    formula: str | None = None
    cell_type: str = "blank"
    merged_range: tuple[int, int, int, int] | None = None
    formatting: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def coordinate(self) -> str:
        """Return Excel-style coordinate for convenience."""

        return f"{_column_letters(self.column + 1)}{self.row + 1}"


@dataclass(slots=True)
class Chart:
    """Basic chart metadata extracted from a Numbers document."""

    sheet_name: str
    chart_id: str
    chart_type: str
    title: str | None = None
    table_name: str | None = None
    series: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TableBlock:
    """A logical Numbers table within a worksheet."""

    name: str
    rows: list[list[Any]] = field(default_factory=list)
    cells: list[Cell] = field(default_factory=list)
    merged_cells: list[tuple[int, int, int, int]] = field(default_factory=list)
    formatting: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def row_count(self) -> int:
        """Return number of materialized rows."""

        return len(self.rows)

    def column_count(self) -> int:
        """Return widest row width."""

        return max((len(row) for row in self.rows), default=0)


@dataclass(slots=True)
class Worksheet:
    """Worksheet containing one or more Numbers tables."""

    name: str
    tables: list[TableBlock] = field(default_factory=list)
    charts: list[Chart] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def all_cells(self) -> list[Cell]:
        """Return all cells across all tables."""

        return [cell for table in self.tables for cell in table.cells]

    def to_rows(self) -> list[list[Any]]:
        """Flatten all tables into CSV/DataFrame-friendly row blocks."""

        if not self.tables:
            return []

        if len(self.tables) == 1:
            return self.tables[0].rows

        merged_rows: list[list[Any]] = []
        for index, table in enumerate(self.tables):
            if index > 0:
                merged_rows.append([])
            merged_rows.append([f"## {table.name}"])
            merged_rows.extend(table.rows)
        return merged_rows

    def primary_table(self) -> TableBlock | None:
        """Return the first table if present."""

        return self.tables[0] if self.tables else None


@dataclass(slots=True)
class Metadata:
    """Workbook-level Numbers metadata."""

    title: str | None = None
    author: str | None = None
    created: str | None = None
    modified: str | None = None
    app_version: str | None = None
    sheet_count: int = 0
    table_count: int = 0
    chart_count: int = 0
    preview_available: bool = False
    archive_entries: list[str] = field(default_factory=list)
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentContent:
    """Fully extracted Numbers workbook content."""

    path: Path
    sheets: list[Worksheet]
    cells: list[Cell]
    formulas: dict[str, str]
    charts: list[Chart]
    metadata: Metadata
    preview_image: bytes | None = None


@dataclass(slots=True)
class _ProtoField:
    """Generic protobuf field decoded from raw wire data."""

    number: int
    wire_type: int
    value: Any


@dataclass(slots=True)
class _DecodedBytes:
    """Length-delimited protobuf field with optional decoded views."""

    raw: bytes
    text: str | None = None
    message: list[_ProtoField] | None = None


class _IWAParser:
    """Low-level parser for IWA archive payloads."""

    def __init__(self, data: bytes):
        self.data = data

    def parse(self) -> list[bytes]:
        """Return decompressed protobuf messages from an IWA payload."""

        if not self.data:
            return []

        raw = self.data[4:] if self.data[:4] == b"IWA1" else self.data
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

        # Fallback: entire file may already be a compressed or raw protobuf blob.
        whole = self._decompress_chunk(raw)
        return [whole] if whole else [raw]

    def _decompress_chunk(self, chunk: bytes) -> bytes:
        """Try multiple Snappy/raw strategies for a chunk."""

        if not chunk:
            return b""

        if chunk.startswith(SNAPPY_STREAM_IDENTIFIER):
            try:
                return self._decompress_snappy_framed(chunk)
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("Failed framed snappy decode: %s", exc)

        if SNAPPY_AVAILABLE:
            for candidate in (chunk, _strip_possible_iwa_header(chunk)):
                if not candidate:
                    continue
                try:
                    return snappy.decompress(candidate)
                except Exception:
                    pass

                try:
                    decompressor = snappy.StreamDecompressor()
                    return decompressor.decompress(candidate)
                except Exception:
                    pass

        return chunk

    def _decompress_snappy_framed(self, chunk: bytes) -> bytes:
        """Decode standard Snappy framed stream payloads."""

        if not SNAPPY_AVAILABLE:
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
                # Compressed data with masked CRC32 prefix.
                output.extend(snappy.decompress(data[4:]))
            elif chunk_type == 0x01:
                # Uncompressed data with masked CRC32 prefix.
                output.extend(data[4:])
            elif 0x80 <= chunk_type <= 0xFE:
                # Skippable chunk.
                continue
            elif chunk_type == 0xFF:
                # Stream identifier, already handled.
                continue

        return bytes(output)


class _ProtoDecoder:
    """Recursive protobuf wire decoder without requiring Apple schemas."""

    def decode(self, data: bytes, depth: int = 0) -> list[_ProtoField]:
        """Decode a protobuf message into field structures."""

        if depth > MAX_PROTO_RECURSION or not data:
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

            fields.append(
                _ProtoField(number=field_number, wire_type=wire_type, value=value)
            )

        return fields

    def _read_value(
        self,
        data: bytes,
        position: int,
        wire_type: int,
        depth: int,
    ) -> tuple[Any, int]:
        """Read one protobuf field value."""

        if wire_type == 0:
            value, position = _read_varint(data, position)
            return value, position

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
                nested = self.decode(blob, depth + 1)
                if not nested:
                    nested = None
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


class NumbersProcessor:
    """Processor for Apple Numbers spreadsheets."""

    def __init__(self, use_textutil_fallback: bool | None = None):
        self.is_macos = platform.system() == "Darwin"
        self.use_textutil_fallback = (
            self.is_macos if use_textutil_fallback is None else use_textutil_fallback
        )
        self._decoder = _ProtoDecoder()
        self._current_document: DocumentContent | None = None

    def parse(self, path: Path | str) -> DocumentContent:
        """Parse a Numbers workbook into structured content."""

        workbook_path = Path(path)
        self._validate_path(workbook_path)

        with zipfile.ZipFile(workbook_path, "r") as archive:
            native_document = self._parse_native(workbook_path, archive)

        if self._should_use_textutil_fallback(native_document):
            try:
                fallback_document = self._parse_with_textutil(workbook_path)
            except Exception as exc:  # pragma: no cover - platform dependent
                logger.debug("textutil fallback failed: %s", exc)
            else:
                if fallback_document.sheets:
                    native_document = self._merge_fallback(
                        native_document, fallback_document
                    )

        self._current_document = native_document
        return native_document

    def get_sheet_names(self) -> list[str]:
        """Return sheet names from the last parsed workbook."""

        document = self._require_document()
        return [sheet.name for sheet in document.sheets]

    def extract_sheet(self, name: str) -> Worksheet:
        """Return one worksheet by name."""

        document = self._require_document()
        for sheet in document.sheets:
            if sheet.name == name:
                return sheet
        raise KeyError(f"Sheet not found: {name}")

    def extract_all_sheets(self) -> list[Worksheet]:
        """Return all extracted worksheets."""

        return list(self._require_document().sheets)

    def extract_cells(self) -> list[Cell]:
        """Return all extracted cells."""

        return list(self._require_document().cells)

    def extract_formulas(self) -> dict[str, str]:
        """Return formulas keyed by sheet/table/cell coordinate."""

        return dict(self._require_document().formulas)

    def extract_charts(self) -> list[Chart]:
        """Return chart metadata extracted from the workbook."""

        return list(self._require_document().charts)

    def extract_metadata(self) -> Metadata:
        """Return workbook metadata from the last parsed workbook."""

        return self._require_document().metadata

    def to_csv(self, sheet: str | Worksheet, output_path: Path | str) -> Path:
        """Export a worksheet to CSV.

        When a sheet contains multiple tables they are flattened into a single
        row stream with empty separator rows and table markers.
        """

        worksheet = self._coerce_sheet(sheet)
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)

        with destination.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            for row in worksheet.to_rows():
                writer.writerow(row)

        return destination

    def to_dataframe(self, sheet: str | Worksheet):
        """Convert a worksheet to a pandas DataFrame."""

        if not PANDAS_AVAILABLE:
            raise ImportError(
                "pandas is required for DataFrame export. Install with: pip install pandas"
            )

        worksheet = self._coerce_sheet(sheet)
        rows = worksheet.to_rows()
        if not rows:
            return pd.DataFrame()

        if len(worksheet.tables) == 1 and rows:
            header = [str(value) for value in rows[0]]
            body = rows[1:] if len(rows) > 1 else []
            return pd.DataFrame(body, columns=header)

        max_width = max((len(row) for row in rows), default=0)
        normalized = [list(row) + [""] * (max_width - len(row)) for row in rows]
        columns = [f"column_{index + 1}" for index in range(max_width)]
        return pd.DataFrame(normalized, columns=columns)

    def get_preview_image(self) -> bytes | None:
        """Return preview image bytes from the last parsed workbook."""

        return self._require_document().preview_image

    def _parse_native(
        self,
        workbook_path: Path,
        archive: zipfile.ZipFile,
    ) -> DocumentContent:
        """Parse Numbers ZIP package using IWA heuristics."""

        archive_entries = archive.namelist()
        preview_image = self._read_preview_image(archive)
        document_strings: list[str] = []
        document_numbers: list[int | float] = []
        plist_metadata: dict[str, Any] = {}

        iwa_payloads: dict[str, list[bytes]] = {}
        for name in archive_entries:
            if name.endswith(".plist"):
                plist_metadata.update(self._read_plist_metadata(archive, name))
            if not name.endswith(".iwa"):
                continue
            try:
                payload = archive.read(name)
            except KeyError:
                continue
            parser = _IWAParser(payload)
            messages = parser.parse()
            iwa_payloads[name] = messages
            if name == "Index/Document.iwa":
                for message in messages:
                    fields = self._decoder.decode(message)
                    document_strings.extend(_collect_strings(fields))
                    document_numbers.extend(_collect_numbers(fields))

        table_files = sorted(
            name
            for name in archive_entries
            if name.startswith("Index/Tables/") and name.endswith(".iwa")
        )

        sheet_names = self._derive_sheet_names(document_strings, len(table_files))
        worksheets: list[Worksheet] = [Worksheet(name=name) for name in sheet_names]
        if not worksheets:
            worksheets = [Worksheet(name=DEFAULT_SHEET_NAME)]

        all_cells: list[Cell] = []
        formulas: dict[str, str] = {}

        for index, table_file in enumerate(table_files):
            messages = iwa_payloads.get(table_file, [])
            worksheet = worksheets[min(index, len(worksheets) - 1)]
            table_name = self._derive_table_name(table_file, index)
            table = self._parse_table_messages(
                messages=messages,
                sheet_name=worksheet.name,
                table_name=table_name,
            )
            if table.cells or table.rows:
                worksheet.tables.append(table)
                all_cells.extend(table.cells)
                formulas.update(self._formula_map_for_table(table))

        charts = self._extract_chart_metadata(
            archive=archive,
            document_strings=document_strings,
            sheet_names=[sheet.name for sheet in worksheets],
        )
        self._attach_charts_to_sheets(worksheets, charts)

        if not any(sheet.tables for sheet in worksheets) and document_strings:
            worksheets = [
                self._build_textual_fallback_sheet(workbook_path, document_strings)
            ]
            all_cells = worksheets[0].all_cells()
            formulas = self._formula_map_for_sheet(worksheets[0])

        metadata = self._build_metadata(
            workbook_path=workbook_path,
            archive_entries=archive_entries,
            preview_image=preview_image,
            plist_metadata=plist_metadata,
            document_strings=document_strings,
            document_numbers=document_numbers,
            worksheets=worksheets,
            charts=charts,
        )

        return DocumentContent(
            path=workbook_path,
            sheets=worksheets,
            cells=all_cells,
            formulas=formulas,
            charts=charts,
            metadata=metadata,
            preview_image=preview_image,
        )

    def _parse_table_messages(
        self,
        messages: list[bytes],
        sheet_name: str,
        table_name: str,
    ) -> TableBlock:
        """Parse one Numbers table tile payload into a table block."""

        candidate_cells: list[Cell] = []
        sequential_values: list[Any] = []
        formatting: dict[str, Any] = {}
        merged_ranges: list[tuple[int, int, int, int]] = []

        for message in messages:
            fields = self._decoder.decode(message)
            candidate_cells.extend(
                self._extract_cells_from_fields(
                    fields=fields,
                    sheet_name=sheet_name,
                    table_name=table_name,
                )
            )
            sequential_values.extend(self._extract_sequential_values(fields))
            formatting.update(self._extract_table_formatting(fields))
            merged_ranges.extend(self._extract_merged_ranges(fields))

        cells = self._normalize_candidate_cells(candidate_cells)
        if not self._cells_look_usable(cells):
            cells = self._build_sequential_cells(
                values=sequential_values,
                sheet_name=sheet_name,
                table_name=table_name,
            )

        rows = self._rows_from_cells(cells)
        merged_ranges = _dedupe_preserve_order(merged_ranges)
        table = TableBlock(
            name=table_name,
            rows=rows,
            cells=cells,
            merged_cells=merged_ranges,
            formatting=formatting,
            metadata={
                "message_count": len(messages),
                "cell_count": len(cells),
                "multiple_tiles": len(messages) > 1,
            },
        )

        self._apply_merged_ranges(table)
        return table

    def _extract_cells_from_fields(
        self,
        fields: list[_ProtoField],
        sheet_name: str,
        table_name: str,
    ) -> list[Cell]:
        """Heuristically identify cell-like protobuf submessages."""

        cells: list[Cell] = []

        def visit(
            message_fields: list[_ProtoField], path: tuple[int, ...] = ()
        ) -> None:
            direct_strings: list[str] = []
            direct_numbers: list[int | float] = []
            formatting: dict[str, Any] = {}

            for proto_field in message_fields:
                value = proto_field.value
                if isinstance(value, _DecodedBytes):
                    if value.text and _is_meaningful_string(value.text):
                        direct_strings.append(value.text)
                        formatting.update(_formatting_from_text(value.text))
                    if value.message:
                        visit(value.message, path + (proto_field.number,))
                elif isinstance(value, (int, float)):
                    direct_numbers.append(value)

            cell = self._build_cell_from_candidate(
                sheet_name=sheet_name,
                table_name=table_name,
                strings=direct_strings,
                numbers=direct_numbers,
                path=path,
                formatting=formatting,
            )
            if cell is not None:
                cells.append(cell)

        visit(fields)
        return cells

    def _build_cell_from_candidate(
        self,
        sheet_name: str,
        table_name: str,
        strings: list[str],
        numbers: list[int | float],
        path: tuple[int, ...],
        formatting: dict[str, Any],
    ) -> Cell | None:
        """Convert a candidate submessage into a Cell when plausible."""

        meaningful_strings = [item for item in strings if _is_meaningful_string(item)]
        if not meaningful_strings and not numbers:
            return None

        small_ints = [
            int(value)
            for value in numbers
            if isinstance(value, int) and 0 <= value <= 1_000_000
        ]
        coordinates = [value for value in small_ints if 0 <= value <= 10_000]
        if len(coordinates) < 2:
            return None

        row = coordinates[0]
        column = coordinates[1]
        if row > 50_000 or column > 16_384:
            return None

        formula = next(
            (item for item in meaningful_strings if _looks_like_formula(item)), None
        )
        non_formula_strings = [item for item in meaningful_strings if item != formula]

        value: Any = None
        display_value = ""
        cell_type = "blank"

        if non_formula_strings:
            display_value = max(non_formula_strings, key=len)
            value = _coerce_scalar(display_value)
            cell_type = _infer_cell_type(value, formula=formula)
        elif formula is not None:
            value = formula
            display_value = formula
            cell_type = "formula"
        elif len(numbers) >= 3:
            numeric_value = numbers[2]
            value = numeric_value
            display_value = str(numeric_value)
            cell_type = _infer_cell_type(numeric_value, formula=None)

        if value in (None, "") and formula is None:
            return None

        merged_range = None
        if len(coordinates) >= 4:
            merged_range = _normalize_range(
                coordinates[0], coordinates[2], coordinates[1], coordinates[3]
            )

        raw = {
            "proto_path": list(path),
            "numbers": numbers[:8],
            "strings": meaningful_strings[:8],
        }

        return Cell(
            sheet_name=sheet_name,
            table_name=table_name,
            row=row,
            column=column,
            value=value,
            display_value=display_value or str(value or ""),
            formula=formula,
            cell_type=cell_type,
            merged_range=merged_range,
            formatting=formatting,
            raw=raw,
        )

    def _extract_sequential_values(self, fields: list[_ProtoField]) -> list[Any]:
        """Collect row-major fallback cell values from decoded protobuf content."""

        values: list[Any] = []
        for text in _collect_strings(fields):
            if not _is_meaningful_string(text):
                continue
            values.append(_coerce_scalar(text))

        if values:
            return _dedupe_preserve_order(values)

        numeric_values = [
            value
            for value in _collect_numbers(fields)
            if isinstance(value, (int, float)) and not isinstance(value, bool)
        ]
        return _dedupe_preserve_order(numeric_values)

    def _extract_table_formatting(self, fields: list[_ProtoField]) -> dict[str, Any]:
        """Extract coarse formatting hints from table payloads."""

        formatting: dict[str, Any] = {}
        for text in _collect_strings(fields):
            formatting.update(_formatting_from_text(text))
        return formatting

    def _extract_merged_ranges(
        self,
        fields: list[_ProtoField],
    ) -> list[tuple[int, int, int, int]]:
        """Extract merged-cell candidates from four-int protobuf tuples."""

        ranges: list[tuple[int, int, int, int]] = []

        def visit(message_fields: list[_ProtoField]) -> None:
            local_ints: list[int] = []
            for proto_field in message_fields:
                value = proto_field.value
                if isinstance(value, int) and 0 <= value <= 10_000:
                    local_ints.append(value)
                elif isinstance(value, _DecodedBytes) and value.message:
                    visit(value.message)

            if len(local_ints) >= 4:
                row1, row2, col1, col2 = local_ints[:4]
                if row2 >= row1 and col2 >= col1 and (row2 > row1 or col2 > col1):
                    ranges.append(_normalize_range(row1, row2, col1, col2))

        visit(fields)
        return ranges

    def _normalize_candidate_cells(self, cells: list[Cell]) -> list[Cell]:
        """Deduplicate and normalize candidate cells."""

        best_by_coordinate: dict[tuple[int, int], Cell] = {}

        for cell in cells:
            key = (cell.row, cell.column)
            current = best_by_coordinate.get(key)
            if current is None or self._score_cell(cell) > self._score_cell(current):
                best_by_coordinate[key] = cell

        normalized = list(best_by_coordinate.values())
        normalized.sort(key=lambda item: (item.row, item.column))

        if normalized:
            min_row = min(cell.row for cell in normalized)
            min_col = min(cell.column for cell in normalized)
            if min_row > 0 or min_col > 0:
                for cell in normalized:
                    cell.row -= min_row
                    cell.column -= min_col

        return normalized

    def _score_cell(self, cell: Cell) -> int:
        """Prefer cells with richer content and formatting."""

        score = 0
        if cell.formula:
            score += 4
        if cell.display_value:
            score += 3
        if cell.cell_type != "blank":
            score += 2
        if cell.formatting:
            score += 1
        return score

    def _cells_look_usable(self, cells: list[Cell]) -> bool:
        """Check whether coordinate-based extraction looks credible."""

        if len(cells) < 2:
            return False

        max_row = max((cell.row for cell in cells), default=0)
        max_col = max((cell.column for cell in cells), default=0)
        if max_row > 50_000 or max_col > 16_384:
            return False

        density = len(cells) / max(1, (max_row + 1) * (max_col + 1))
        return density > 0.01 or len(cells) >= 8

    def _build_sequential_cells(
        self,
        values: list[Any],
        sheet_name: str,
        table_name: str,
    ) -> list[Cell]:
        """Build cells when explicit row/column coordinates are unavailable."""

        clean_values = [value for value in values if value not in ("", None)]
        if not clean_values:
            return []

        column_count = self._guess_column_count(clean_values)
        cells: list[Cell] = []

        for index, value in enumerate(clean_values):
            row = index // column_count
            column = index % column_count
            formula = (
                value if isinstance(value, str) and _looks_like_formula(value) else None
            )
            cells.append(
                Cell(
                    sheet_name=sheet_name,
                    table_name=table_name,
                    row=row,
                    column=column,
                    value=value,
                    display_value=str(value),
                    formula=formula,
                    cell_type=_infer_cell_type(value, formula=formula),
                )
            )

        return cells

    def _guess_column_count(self, values: list[Any]) -> int:
        """Guess a reasonable fallback column count."""

        total = len(values)
        if total <= 1:
            return 1
        if total <= 4:
            return min(total, 2)

        root = max(2, int(math.sqrt(total)))
        candidates = sorted(
            {2, 3, 4, 5, 6, 8, 10, 12, root, min(MAX_TABLE_COLUMNS, root + 1)}
        )
        best = 4
        best_score = -1.0

        for candidate in candidates:
            rows = math.ceil(total / candidate)
            raggedness = abs((rows * candidate) - total)
            score = candidate - raggedness
            if score > best_score:
                best_score = score
                best = candidate

        return max(1, min(best, MAX_TABLE_COLUMNS))

    def _rows_from_cells(self, cells: list[Cell]) -> list[list[Any]]:
        """Materialize a 2D row grid from cell coordinates."""

        if not cells:
            return []

        max_row = max(cell.row for cell in cells)
        max_col = max(cell.column for cell in cells)
        grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]

        for cell in cells:
            grid[cell.row][cell.column] = (
                cell.value if cell.value is not None else cell.display_value
            )

        while grid and all(item in ("", None) for item in grid[-1]):
            grid.pop()

        return [self._trim_row(row) for row in grid]

    def _trim_row(self, row: list[Any]) -> list[Any]:
        """Trim trailing empty cells from a row."""

        trimmed = list(row)
        while trimmed and trimmed[-1] in ("", None):
            trimmed.pop()
        return trimmed

    def _apply_merged_ranges(self, table: TableBlock) -> None:
        """Annotate cells with merged-range metadata where possible."""

        if not table.merged_cells:
            return

        cell_map = {(cell.row, cell.column): cell for cell in table.cells}
        for merged_range in table.merged_cells:
            row_start, row_end, col_start, col_end = merged_range
            origin = cell_map.get((row_start, col_start))
            if origin is not None:
                origin.merged_range = merged_range

    def _formula_map_for_table(self, table: TableBlock) -> dict[str, str]:
        """Build formula mapping for one table."""

        formulas: dict[str, str] = {}
        for cell in table.cells:
            if cell.formula:
                key = f"{cell.sheet_name}/{table.name}/{cell.coordinate}"
                formulas[key] = cell.formula
        return formulas

    def _formula_map_for_sheet(self, sheet: Worksheet) -> dict[str, str]:
        """Build formula mapping for all tables in one sheet."""

        formulas: dict[str, str] = {}
        for table in sheet.tables:
            formulas.update(self._formula_map_for_table(table))
        return formulas

    def _extract_chart_metadata(
        self,
        archive: zipfile.ZipFile,
        document_strings: list[str],
        sheet_names: list[str],
    ) -> list[Chart]:
        """Extract basic chart metadata from workbook strings and assets."""

        charts: list[Chart] = []
        chart_like_strings = [
            text for text in document_strings if CHART_TYPE_RE.search(text)
        ]

        for index, text in enumerate(chart_like_strings):
            match = CHART_TYPE_RE.search(text)
            if not match:
                continue
            chart_type = match.group(1).lower()
            sheet_name = (
                sheet_names[min(index, len(sheet_names) - 1)]
                if sheet_names
                else DEFAULT_SHEET_NAME
            )
            charts.append(
                Chart(
                    sheet_name=sheet_name,
                    chart_id=f"chart-{index + 1}",
                    chart_type=chart_type,
                    title=text if len(text) <= 120 else text[:117] + "...",
                    metadata={"source": "document_strings"},
                )
            )

        if charts:
            return charts

        data_assets = [name for name in archive.namelist() if name.startswith("Data/")]
        for index, name in enumerate(data_assets):
            lower_name = name.lower()
            if "chart" not in lower_name:
                continue
            chart_type_match = CHART_TYPE_RE.search(lower_name)
            chart_type = (
                chart_type_match.group(1).lower() if chart_type_match else "chart"
            )
            sheet_name = (
                sheet_names[min(index, len(sheet_names) - 1)]
                if sheet_names
                else DEFAULT_SHEET_NAME
            )
            charts.append(
                Chart(
                    sheet_name=sheet_name,
                    chart_id=f"chart-{index + 1}",
                    chart_type=chart_type,
                    title=Path(name).stem,
                    metadata={"asset_path": name},
                )
            )

        return charts

    def _attach_charts_to_sheets(
        self,
        worksheets: list[Worksheet],
        charts: list[Chart],
    ) -> None:
        """Attach charts to matching worksheet objects."""

        sheet_map = {sheet.name: sheet for sheet in worksheets}
        for chart in charts:
            sheet = sheet_map.get(chart.sheet_name)
            if sheet is not None:
                sheet.charts.append(chart)

    def _build_textual_fallback_sheet(
        self,
        workbook_path: Path,
        document_strings: list[str],
    ) -> Worksheet:
        """Create one worksheet from generic document strings."""

        table = self._parse_delimited_text_table(document_strings, table_name="Table 1")
        if table is None:
            table = TableBlock(
                name="Table 1",
                rows=[
                    [text]
                    for text in _dedupe_preserve_order(document_strings)
                    if _is_meaningful_string(text)
                ],
            )
            table.cells = self._cells_from_rows(
                sheet_name=workbook_path.stem or DEFAULT_SHEET_NAME,
                table_name=table.name,
                rows=table.rows,
            )

        return Worksheet(
            name=workbook_path.stem or DEFAULT_SHEET_NAME,
            tables=[table],
            metadata={"fallback": "document_strings"},
        )

    def _build_metadata(
        self,
        workbook_path: Path,
        archive_entries: list[str],
        preview_image: bytes | None,
        plist_metadata: dict[str, Any],
        document_strings: list[str],
        document_numbers: list[int | float],
        worksheets: list[Worksheet],
        charts: list[Chart],
    ) -> Metadata:
        """Build workbook metadata from all available sources."""

        raw_metadata = dict(plist_metadata)
        raw_metadata["document_strings_sample"] = document_strings[:25]
        raw_metadata["document_numbers_sample"] = document_numbers[:25]

        title = _first_non_empty(
            _string_value(plist_metadata.get("title")),
            _string_value(plist_metadata.get("Title")),
            workbook_path.stem,
        )
        author = _first_non_empty(
            _string_value(plist_metadata.get("author")),
            _string_value(plist_metadata.get("Author")),
            _extract_authorish_string(document_strings),
        )
        created = _first_non_empty(
            _string_value(plist_metadata.get("created")),
            _string_value(plist_metadata.get("CreationDate")),
        )
        modified = _first_non_empty(
            _string_value(plist_metadata.get("modified")),
            _string_value(plist_metadata.get("ModificationDate")),
        )
        app_version = _first_non_empty(
            _string_value(plist_metadata.get("app_version")),
            _extract_app_version(document_strings),
        )

        return Metadata(
            title=title,
            author=author,
            created=created,
            modified=modified,
            app_version=app_version,
            sheet_count=len(worksheets),
            table_count=sum(len(sheet.tables) for sheet in worksheets),
            chart_count=len(charts),
            preview_available=preview_image is not None,
            archive_entries=archive_entries,
            raw_metadata=raw_metadata,
        )

    def _read_plist_metadata(
        self, archive: zipfile.ZipFile, name: str
    ) -> dict[str, Any]:
        """Read plist metadata from a ZIP entry."""

        try:
            raw = archive.read(name)
        except KeyError:
            return {}

        try:
            parsed = plistlib.loads(raw)
        except Exception:
            return {}

        if isinstance(parsed, dict):
            return _flatten_mapping(parsed)
        return {}

    def _read_preview_image(self, archive: zipfile.ZipFile) -> bytes | None:
        """Read preview image from common Numbers preview locations."""

        for name in archive.namelist():
            lower_name = name.lower()
            if lower_name == "preview.jpg" or (
                "preview" in lower_name
                and lower_name.endswith((".jpg", ".jpeg", ".png"))
            ):
                try:
                    return archive.read(name)
                except KeyError:
                    return None
        return None

    def _derive_sheet_names(
        self, document_strings: list[str], table_count: int
    ) -> list[str]:
        """Infer sheet names from Document.iwa strings."""

        candidates: list[str] = []
        for text in document_strings:
            if not _is_sheet_name_candidate(text):
                continue
            candidates.append(text.strip())

        candidates = _dedupe_preserve_order(candidates)
        if table_count <= 0:
            table_count = max(1, len(candidates))

        if not candidates:
            return [DEFAULT_SHEET_NAME] + [
                f"Sheet {index}" for index in range(2, table_count + 1)
            ]

        if len(candidates) < table_count:
            start = len(candidates) + 1
            candidates.extend(
                f"Sheet {index}" for index in range(start, table_count + 1)
            )

        return candidates[:table_count] if table_count else candidates

    def _derive_table_name(self, table_file: str, index: int) -> str:
        """Derive a stable human-readable table name from a tile path."""

        stem = Path(table_file).stem
        suffix = stem.split("Tile-", 1)[-1]
        suffix = suffix.replace("-", "_")
        return (
            f"Table {index + 1}"
            if not suffix or suffix == stem
            else f"Table {index + 1} ({suffix})"
        )

    def _parse_with_textutil(self, workbook_path: Path) -> DocumentContent:
        """Fallback parser using macOS textutil output."""

        if not self.is_macos or not self.use_textutil_fallback:
            raise NumbersUnsupportedError(
                "textutil fallback is only available on macOS"
            )

        textutil_path = shutil.which("textutil")
        if not textutil_path:
            raise NumbersUnsupportedError("textutil executable not found")

        result = subprocess.run(
            [textutil_path, "-convert", "txt", "-stdout", str(workbook_path)],
            capture_output=True,
            text=True,
            timeout=TEXTUTIL_TIMEOUT,
            check=False,
        )
        if result.returncode != 0:
            raise NumbersCorruptedError(
                result.stderr or result.stdout or "textutil failed"
            )

        text = result.stdout.strip()
        sheet = self._worksheet_from_text(text, workbook_path)
        metadata = Metadata(
            title=workbook_path.stem,
            sheet_count=1 if sheet.tables else 0,
            table_count=len(sheet.tables),
            chart_count=0,
            preview_available=False,
            archive_entries=[],
            raw_metadata={"fallback": "textutil"},
        )
        formulas = self._formula_map_for_sheet(sheet)
        charts: list[Chart] = []

        return DocumentContent(
            path=workbook_path,
            sheets=[sheet] if sheet.tables else [],
            cells=sheet.all_cells(),
            formulas=formulas,
            charts=charts,
            metadata=metadata,
            preview_image=None,
        )

    def _worksheet_from_text(self, text: str, workbook_path: Path) -> Worksheet:
        """Create a worksheet from textutil output."""

        blocks = [
            block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()
        ]
        tables: list[TableBlock] = []

        for index, block in enumerate(blocks, start=1):
            lines = [line.rstrip() for line in block.splitlines() if line.strip()]
            if not lines:
                continue
            table = self._parse_delimited_text_table(lines, table_name=f"Table {index}")
            if table is None:
                rows = [[line] for line in lines]
                table = TableBlock(name=f"Table {index}", rows=rows)
                table.cells = self._cells_from_rows(
                    sheet_name=workbook_path.stem or DEFAULT_SHEET_NAME,
                    table_name=table.name,
                    rows=rows,
                )
            tables.append(table)

        return Worksheet(
            name=workbook_path.stem or DEFAULT_SHEET_NAME,
            tables=tables,
            metadata={"fallback": "textutil"},
        )

    def _parse_delimited_text_table(
        self,
        lines: Iterable[str],
        table_name: str,
    ) -> TableBlock | None:
        """Try to parse a delimited text block into a table."""

        lines = list(lines)
        if not lines:
            return None

        delimiter = self._guess_delimiter(lines)
        if delimiter is None:
            return None

        rows = list(csv.reader(lines, delimiter=delimiter))
        rows = [row for row in rows if row]
        if not rows:
            return None

        table = TableBlock(name=table_name, rows=rows)
        table.cells = self._cells_from_rows(
            sheet_name=DEFAULT_SHEET_NAME,
            table_name=table_name,
            rows=rows,
        )
        return table

    def _guess_delimiter(self, lines: list[str]) -> str | None:
        """Guess a delimiter for textutil output."""

        delimiters = [",", "\t", ";", "|"]
        scores = dict.fromkeys(delimiters, 0)

        for line in lines[:20]:
            for delimiter in delimiters:
                count = line.count(delimiter)
                if count > 0:
                    scores[delimiter] += count

        delimiter, score = max(scores.items(), key=lambda item: item[1])
        return delimiter if score > 0 else None

    def _cells_from_rows(
        self,
        sheet_name: str,
        table_name: str,
        rows: list[list[Any]],
    ) -> list[Cell]:
        """Create Cell objects from an already materialized row grid."""

        cells: list[Cell] = []
        for row_index, row in enumerate(rows):
            for col_index, value in enumerate(row):
                formula = (
                    value
                    if isinstance(value, str) and _looks_like_formula(value)
                    else None
                )
                cells.append(
                    Cell(
                        sheet_name=sheet_name,
                        table_name=table_name,
                        row=row_index,
                        column=col_index,
                        value=value,
                        display_value=str(value),
                        formula=formula,
                        cell_type=_infer_cell_type(value, formula=formula),
                    )
                )
        return cells

    def _merge_fallback(
        self,
        native_document: DocumentContent,
        fallback_document: DocumentContent,
    ) -> DocumentContent:
        """Merge textutil fallback when native extraction is sparse."""

        if native_document.sheets:
            native_has_tables = any(sheet.tables for sheet in native_document.sheets)
            if native_has_tables:
                return native_document

        return DocumentContent(
            path=native_document.path,
            sheets=fallback_document.sheets or native_document.sheets,
            cells=fallback_document.cells or native_document.cells,
            formulas=fallback_document.formulas or native_document.formulas,
            charts=native_document.charts,
            metadata=self._merged_metadata(
                native_document.metadata, fallback_document.metadata
            ),
            preview_image=native_document.preview_image
            or fallback_document.preview_image,
        )

    def _merged_metadata(self, primary: Metadata, fallback: Metadata) -> Metadata:
        """Merge metadata preferring primary/native values."""

        raw_metadata = dict(fallback.raw_metadata)
        raw_metadata.update(primary.raw_metadata)
        return Metadata(
            title=primary.title or fallback.title,
            author=primary.author or fallback.author,
            created=primary.created or fallback.created,
            modified=primary.modified or fallback.modified,
            app_version=primary.app_version or fallback.app_version,
            sheet_count=primary.sheet_count or fallback.sheet_count,
            table_count=primary.table_count or fallback.table_count,
            chart_count=primary.chart_count or fallback.chart_count,
            preview_available=primary.preview_available or fallback.preview_available,
            archive_entries=primary.archive_entries or fallback.archive_entries,
            raw_metadata=raw_metadata,
        )

    def _should_use_textutil_fallback(self, document: DocumentContent) -> bool:
        """Determine whether textutil fallback should be attempted."""

        if not self.use_textutil_fallback or not self.is_macos:
            return False

        if not document.sheets:
            return True

        if not any(sheet.tables for sheet in document.sheets):
            return True

        return len(document.cells) <= 1 and not document.formulas

    def _validate_path(self, workbook_path: Path) -> None:
        """Validate Numbers path."""

        if not workbook_path.exists():
            raise NumbersNotFoundError(f"File not found: {workbook_path}")
        if workbook_path.suffix.lower() != ".numbers":
            raise NumbersUnsupportedError(
                f"Expected a .numbers file, got: {workbook_path.suffix or '<no extension>'}"
            )
        if not zipfile.is_zipfile(workbook_path):
            raise NumbersCorruptedError(
                f"Not a valid Numbers ZIP package: {workbook_path}"
            )

    def _require_document(self) -> DocumentContent:
        """Require that parse() has already been called."""

        if self._current_document is None:
            raise NumbersError(
                "No workbook has been parsed yet. Call parse(path) first."
            )
        return self._current_document

    def _coerce_sheet(self, sheet: str | Worksheet) -> Worksheet:
        """Resolve a sheet argument into a Worksheet instance."""

        if isinstance(sheet, Worksheet):
            return sheet
        return self.extract_sheet(sheet)


def _read_varint(data: bytes, position: int) -> tuple[int, int]:
    """Read a protobuf varint starting at position."""

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
    """Choose a more human-meaningful numeric representation."""

    if math.isfinite(float_value) and not math.isnan(float_value):
        if abs(float_value) > 0 and abs(float_value) < 1e12:
            if not float_value.is_integer():
                return float_value
    return int_value


def _strip_possible_iwa_header(data: bytes) -> bytes:
    """Strip small wrapper headers sometimes seen in IWA chunks."""

    if len(data) > 8 and data[:4] == b"IWA1":
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
    """Decode a bytes blob to UTF-8 text if it looks text-like."""

    if not data or len(data) > 4096:
        return None
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return None

    cleaned = text.strip("\x00\r\n\t ")
    return cleaned if _is_meaningful_string(cleaned) else None


def _collect_strings(fields: list[_ProtoField]) -> list[str]:
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


def _collect_numbers(fields: list[_ProtoField]) -> list[int | float]:
    """Collect scalar numbers from a protobuf field tree."""

    values: list[int | float] = []
    for proto_field in fields:
        value = proto_field.value
        if isinstance(value, (int, float)):
            values.append(value)
        elif isinstance(value, _DecodedBytes) and value.message:
            values.extend(_collect_numbers(value.message))
    return values


def _coerce_scalar(value: Any) -> Any:
    """Convert text scalars to richer Python values where obvious."""

    if not isinstance(value, str):
        return value

    text = value.strip()
    if not text:
        return ""

    lower = text.lower()
    if lower in {"true", "yes"}:
        return True
    if lower in {"false", "no"}:
        return False

    if DATE_RE.match(text):
        return text

    integer_candidate = text.replace(",", "")
    if re.fullmatch(r"[-+]?\d+", integer_candidate):
        try:
            return int(integer_candidate)
        except ValueError:
            pass

    float_candidate = integer_candidate.rstrip("%")
    if re.fullmatch(r"[-+]?\d+\.\d+", float_candidate):
        try:
            return float(float_candidate)
        except ValueError:
            pass

    return text


def _infer_cell_type(value: Any, formula: str | None) -> str:
    """Infer a coarse cell type."""

    if formula is not None:
        return "formula"
    if value in ("", None):
        return "blank"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str) and DATE_RE.match(value):
        return "date"
    return "text"


def _formatting_from_text(text: str) -> dict[str, Any]:
    """Extract minimal formatting hints from textual metadata."""

    formatting: dict[str, Any] = {}

    colors = HEX_COLOR_RE.findall(text)
    if colors:
        formatting["colors"] = colors

    lowered = text.lower()
    for keyword in ALIGNMENT_KEYWORDS:
        if keyword in lowered:
            formatting["alignment"] = keyword
            break

    font_match = re.search(r"\bfont(?: size)?[:= ]+(\d+(?:\.\d+)?)", lowered)
    if font_match:
        formatting["font_size"] = float(font_match.group(1))

    if "bold" in lowered:
        formatting["bold"] = True
    if "italic" in lowered:
        formatting["italic"] = True
    if "underline" in lowered:
        formatting["underline"] = True

    return formatting


def _normalize_range(
    row_start: int,
    row_end: int,
    col_start: int,
    col_end: int,
) -> tuple[int, int, int, int]:
    """Normalize a row/column cell range tuple."""

    return (
        min(row_start, row_end),
        max(row_start, row_end),
        min(col_start, col_end),
        max(col_start, col_end),
    )


def _is_meaningful_string(text: str) -> bool:
    """Check whether a decoded string is likely user-relevant content."""

    if not text:
        return False
    cleaned = text.strip()
    if len(cleaned) < 1:
        return False
    if cleaned in SYSTEMISH_STRINGS:
        return False
    if cleaned.startswith("/") or cleaned.endswith(".iwa"):
        return False
    if len(cleaned) > 512:
        return False

    printable_ratio = sum(char.isprintable() for char in cleaned) / len(cleaned)
    if printable_ratio < 0.9:
        return False

    if any(char.isalpha() for char in cleaned):
        return True

    if _looks_like_formula(cleaned):
        return True

    if cleaned.lower() in BOOL_STRINGS:
        return True

    return bool(re.fullmatch(r"[-+]?\d+(?:\.\d+)?%?", cleaned))


def _looks_like_formula(text: str) -> bool:
    """Return True if text looks like a spreadsheet formula."""

    return bool(FORMULA_RE.match(text.strip()))


def _is_sheet_name_candidate(text: str) -> bool:
    """Heuristic filter for sheet names from document-level strings."""

    if not _is_meaningful_string(text):
        return False

    cleaned = text.strip()
    if len(cleaned) > 64:
        return False
    if _looks_like_formula(cleaned):
        return False
    if "\n" in cleaned or "\t" in cleaned:
        return False
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?", cleaned):
        return False
    return not cleaned.lower().startswith(("http://", "https://"))


def _extract_authorish_string(strings: list[str]) -> str | None:
    """Find the first string that resembles an author identity."""

    for text in strings:
        if "@" in text and len(text) <= 128:
            return text
    return None


def _extract_app_version(strings: list[str]) -> str | None:
    """Find a Numbers version-like string."""

    for text in strings:
        if "numbers" in text.lower() and any(char.isdigit() for char in text):
            return text
    return None


def _first_non_empty(*values: str | None) -> str | None:
    """Return the first non-empty string."""

    for value in values:
        if value:
            return value
    return None


def _string_value(value: Any) -> str | None:
    """Convert metadata values to strings."""

    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return None


def _flatten_mapping(mapping: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten nested plist dictionaries to a simple mapping."""

    flat: dict[str, Any] = {}
    for key, value in mapping.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flat.update(_flatten_mapping(value, prefix=full_key))
        else:
            flat[key] = value
            flat[full_key] = value
    return flat


def _dedupe_preserve_order(values: Iterable[Any]) -> list[Any]:
    """Deduplicate while preserving order."""

    seen: set[Any] = set()
    result: list[Any] = []
    for value in values:
        key = (
            value if isinstance(value, (str, int, float, bool, tuple)) else repr(value)
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _column_letters(index: int) -> str:
    """Convert a 1-based column index to spreadsheet letters."""

    letters: list[str] = []
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters.append(chr(65 + remainder))
    return "".join(reversed(letters)) or "A"


def extract_text(path: Path | str) -> DocumentContent:
    """Convenience wrapper for parsing a Numbers workbook."""

    processor = NumbersProcessor()
    return processor.parse(path)


__all__ = [
    "Cell",
    "Chart",
    "DocumentContent",
    "Metadata",
    "NumbersCorruptedError",
    "NumbersError",
    "NumbersNotFoundError",
    "NumbersProcessor",
    "NumbersUnsupportedError",
    "TableBlock",
    "Worksheet",
    "extract_text",
]
