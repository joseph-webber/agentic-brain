# SPDX-License-Identifier: Apache-2.0

"""Data models for office document processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Dict, List, Optional, Sequence


class OfficeFormat(StrEnum):
    """Supported office document container formats."""

    DOCX = "docx"
    XLSX = "xlsx"
    PPTX = "pptx"
    PAGES = "pages"
    NUMBERS = "numbers"
    KEYNOTE = "keynote"
    ODT = "odt"
    ODS = "ods"
    ODP = "odp"
    RTF = "rtf"


@dataclass(slots=True)
class DocumentStyle:
    """Style definition applied to text, shapes, and other elements."""

    font_family: str = "Calibri"
    font_size: float = 12.0
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    text_color: str = "#000000"
    background_color: str = "#FFFFFF"
    alignment: str = "left"
    line_spacing: float = 1.15
    spacing_before: float = 0.0
    spacing_after: float = 0.0
    indentation_left: float = 0.0
    indentation_right: float = 0.0
    indentation_first_line: float = 0.0
    styles: Dict[str, str | float | bool] = field(default_factory=dict)


@dataclass(slots=True)
class Metadata:
    """Document metadata describing provenance and properties."""

    title: Optional[str] = None
    subject: Optional[str] = None
    author: Optional[str] = None
    company: Optional[str] = None
    category: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    last_printed_at: Optional[datetime] = None
    revision: Optional[str] = None
    custom_properties: Dict[str, str | int | float | bool | datetime] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class TextRun:
    """Smallest text segment with its own formatting."""

    text: str
    style: DocumentStyle = field(default_factory=DocumentStyle)
    language: Optional[str] = None
    hyperlink: Optional[str] = None
    alternate_text: Optional[str] = None


@dataclass(slots=True)
class Paragraph:
    """Paragraph containing one or multiple text runs."""

    runs: List[TextRun] = field(default_factory=list)
    style: DocumentStyle = field(default_factory=DocumentStyle)
    paragraph_id: Optional[str] = None
    numbering_level: Optional[int] = None
    numbering_id: Optional[str] = None
    is_heading: bool = False
    heading_level: Optional[int] = None
    comments: List[Comment] = field(default_factory=list)
    bookmarked: bool = False
    bookmark_id: Optional[str] = None

    def text_content(self) -> str:
        """Return the plain text representation of the paragraph."""

        return "".join(run.text for run in self.runs)

    def add_run(self, run: TextRun) -> None:
        """Append a text run to the paragraph."""

        self.runs.append(run)


@dataclass(slots=True)
class TableCell:
    """Single cell in a table."""

    paragraphs: List[Paragraph] = field(default_factory=list)
    rowspan: int = 1
    colspan: int = 1
    width: Optional[float] = None
    height: Optional[float] = None
    style: DocumentStyle = field(default_factory=DocumentStyle)
    shading_color: Optional[str] = None
    borders: Dict[str, Dict[str, str | float]] = field(default_factory=dict)
    cell_id: Optional[str] = None

    def add_paragraph(self, paragraph: Paragraph) -> None:
        """Append a paragraph into the cell."""

        self.paragraphs.append(paragraph)

    def text_content(self) -> str:
        """Plain text content of the cell."""

        return "\n".join(paragraph.text_content() for paragraph in self.paragraphs)


@dataclass(slots=True)
class Table:
    """Table representation supporting merged cells and embedded objects."""

    rows: List[List[TableCell]] = field(default_factory=list)
    width: Optional[float] = None
    alignment: str = "left"
    style: DocumentStyle = field(default_factory=DocumentStyle)
    has_header_row: bool = False
    has_total_row: bool = False
    cell_grid: Dict[str, TableCell] = field(default_factory=dict)
    captions: List[Paragraph] = field(default_factory=list)
    table_id: Optional[str] = None

    def add_row(self, cells: Sequence[TableCell]) -> None:
        """Add a new row to the table."""

        self.rows.append(list(cells))

    def iter_cells(self) -> Sequence[TableCell]:
        """Yield all cells in row-major order."""

        for row in self.rows:
            yield from row

    def get_cell(self, row_index: int, column_index: int) -> Optional[TableCell]:
        """Return cell by zero-based coordinates."""

        if row_index < 0 or column_index < 0:
            return None
        try:
            return self.rows[row_index][column_index]
        except IndexError:
            return None


@dataclass(slots=True)
class Image:
    """Embedded raster image with metadata."""

    data: bytes
    mime_type: str
    description: Optional[str] = None
    width: Optional[float] = None
    height: Optional[float] = None
    title: Optional[str] = None
    alternate_text: Optional[str] = None
    anchor_paragraph: Optional[str] = None
    position: Dict[str, float] = field(default_factory=dict)
    properties: Dict[str, str | float | bool] = field(default_factory=dict)

    def as_data_uri(self) -> Optional[str]:
        """Return base64 encoded data URI if possible."""

        if not self.mime_type.startswith("image/"):
            return None
        try:
            import base64

            encoded = base64.b64encode(self.data).decode("ascii")
        except Exception:  # pragma: no cover - defensive
            return None
        return f"data:{self.mime_type};base64,{encoded}"


@dataclass(slots=True)
class Shape:
    """Vector shape primitive (lines, rectangles, connectors, etc.)."""

    shape_type: str
    path: Sequence[Dict[str, str | float]]
    fill_color: Optional[str] = None
    stroke_color: Optional[str] = None
    stroke_width: float = 1.0
    text: Optional[Paragraph] = None
    style: DocumentStyle = field(default_factory=DocumentStyle)
    properties: Dict[str, str | float | bool] = field(default_factory=dict)
    rotation: float = 0.0
    z_index: int = 0


@dataclass(slots=True)
class Chart:
    """Embedded chart with series description and rendering hints."""

    chart_type: str
    title: Optional[str] = None
    series: List[Dict[str, str | float | List[float] | List[str]]] = field(
        default_factory=list
    )
    categories: List[str] = field(default_factory=list)
    legend: Dict[str, str | bool] = field(default_factory=dict)
    style: DocumentStyle = field(default_factory=DocumentStyle)
    position: Dict[str, float] = field(default_factory=dict)
    axis_titles: Dict[str, Optional[str]] = field(
        default_factory=lambda: {"x": None, "y": None}
    )
    data_range: Optional[str] = None

    def add_series(
        self, name: str, values: Sequence[float], colors: Optional[Sequence[str]] = None
    ) -> None:
        """Append a series definition."""

        entry: Dict[str, str | float | List[float] | List[str]] = {
            "name": name,
            "values": list(values),
        }
        if colors:
            entry["colors"] = list(colors)
        self.series.append(entry)


@dataclass(slots=True)
class Comment:
    """Annotation on a document element."""

    author: str
    text: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    resolved: bool = False
    replies: List[Comment] = field(default_factory=list)
    target_id: Optional[str] = None
    metadata: Dict[str, str | int | bool] = field(default_factory=dict)

    def add_reply(self, reply: Comment) -> None:
        """Attach a reply to this comment."""

        self.replies.append(reply)

    def mark_resolved(self) -> None:
        """Mark the comment resolved."""

        self.resolved = True


@dataclass(slots=True)
class Cell:
    """Spreadsheet cell with value and formula metadata."""

    reference: str
    value: Optional[str | float | int | bool | datetime] = None
    formula: Optional[str] = None
    style: DocumentStyle = field(default_factory=DocumentStyle)
    comment: Optional[Comment] = None
    data_validation: Dict[str, str | float | bool] = field(default_factory=dict)
    hyperlink: Optional[str] = None
    merged: bool = False
    merge_range: Optional[str] = None
    number_format: Optional[str] = None
    errors: List[str] = field(default_factory=list)

    def set_value(self, value: str | float | int | bool | datetime | None) -> None:
        """Update the cell value and clear any errors."""

        self.value = value
        self.errors.clear()

    def add_error(self, error_msg: str) -> None:
        """Track a validation or calculation error."""

        self.errors.append(error_msg)


@dataclass(slots=True)
class Worksheet:
    """Spreadsheet worksheet definition."""

    name: str
    cells: Dict[str, Cell] = field(default_factory=dict)
    column_widths: Dict[int, float] = field(default_factory=dict)
    row_heights: Dict[int, float] = field(default_factory=dict)
    frozen_panes: Optional[str] = None
    tab_color: Optional[str] = None
    charts: List[Chart] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    protection: Dict[str, str | bool] = field(default_factory=dict)

    def set_cell(self, cell: Cell) -> None:
        """Insert or replace a cell."""

        self.cells[cell.reference] = cell

    def get_cell(self, reference: str) -> Optional[Cell]:
        """Retrieve a cell by reference."""

        return self.cells.get(reference)

    def iter_cells(self) -> Sequence[Cell]:
        """Yield all cells in the worksheet."""

        return self.cells.values()


@dataclass(slots=True)
class Slide:
    """Presentation slide containing text, shapes, tables, and images."""

    title: Optional[Paragraph] = None
    body: List[Paragraph] = field(default_factory=list)
    notes: List[Paragraph] = field(default_factory=list)
    images: List[Image] = field(default_factory=list)
    shapes: List[Shape] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    charts: List[Chart] = field(default_factory=list)
    background: Optional[str] = None
    layout_name: Optional[str] = None
    transition: Optional[Dict[str, str | float]] = None
    master_slide_name: Optional[str] = None

    def all_elements(self) -> List[DocumentElement]:
        """Return a flattened list of all slide elements."""

        elements: List[DocumentElement] = []
        elements.extend(self.body)
        elements.extend(self.notes)
        elements.extend(self.images)
        elements.extend(self.shapes)
        elements.extend(self.tables)
        elements.extend(self.charts)
        if self.title:
            elements.append(self.title)
        return elements


@dataclass(slots=True)
class DocumentContent:
    """Unified document container bridging word processing, slides, and spreadsheets."""

    format: OfficeFormat
    paragraphs: List[Paragraph] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    images: List[Image] = field(default_factory=list)
    shapes: List[Shape] = field(default_factory=list)
    slides: List[Slide] = field(default_factory=list)
    worksheets: List[Worksheet] = field(default_factory=list)
    charts: List[Chart] = field(default_factory=list)
    comments: List[Comment] = field(default_factory=list)
    metadata: Metadata = field(default_factory=Metadata)
    styles: Dict[str, DocumentStyle] = field(default_factory=dict)
    document_properties: Dict[str, str | float | bool] = field(default_factory=dict)
    resources: Dict[str, bytes] = field(default_factory=dict)
    sections: List[str] = field(default_factory=list)


# Convenience alias for mixed content collections used in serializers and processors.
DocumentElement = (
    Paragraph | Table | Image | Shape | Slide | Worksheet | Chart | Comment
)
