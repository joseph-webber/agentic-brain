# SPDX-License-Identifier: Apache-2.0

"""OpenDocument processing built on top of odfpy.

This module implements :class:`OpenDocumentProcessor`, a shared processor for
OpenDocument Text (``.odt``), Spreadsheet (``.ods``), and Presentation
(``.odp``) files. The processor follows the same normalization strategy as the
other office processors in this package and maps extracted content into the
shared models from :mod:`agentic_brain.documents.services.office.models`.

Highlights
----------
- format detection using extension, ODF mimetype, and archive structure
- full text extraction for Writer, Calc, and Impress documents
- structured paragraph extraction across all supported ODF formats
- table extraction integrated with :class:`.tables.TableExtractor`
- image extraction from the standard ``Pictures/`` package folder
- metadata extraction from the ODF ``meta`` section
- normalized :class:`DocumentContent` output for downstream RAG pipelines
"""

from __future__ import annotations

import logging
import mimetypes
import re
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from xml.etree import ElementTree as ET

from .exceptions import DocumentValidationError, UnsupportedOfficeFormatError
from .models import (
    Cell,
    DocumentContent,
    DocumentStyle,
    Image,
    Metadata,
    OfficeFormat,
    Paragraph,
    Slide,
    Table,
    TableCell,
    TextRun,
    Worksheet,
)
from .tables import Cell as ExtractedCell
from .tables import Table as ExtractedTable
from .tables import TableExtractor

try:  # pragma: no cover - optional dependency boundary
    from odf import draw, office, opendocument, style, table, text
    from odf.element import Element
    from odf.teletype import extractText

    ODF_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency boundary
    draw = office = opendocument = style = table = text = None
    Element = Any

    def extractText(_element: Any) -> str:
        return ""

    ODF_AVAILABLE = False

logger = logging.getLogger(__name__)

ODF_NS = {
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
    "meta": "urn:oasis:names:tc:opendocument:xmlns:meta:1.0",
    "dc": "http://purl.org/dc/elements/1.1/",
    "draw": "urn:oasis:names:tc:opendocument:xmlns:drawing:1.0",
    "svg": "urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0",
    "style": "urn:oasis:names:tc:opendocument:xmlns:style:1.0",
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "manifest": "urn:oasis:names:tc:opendocument:xmlns:manifest:1.0",
}

ODF_MIMETYPE_TO_FORMAT = {
    "application/vnd.oasis.opendocument.text": OfficeFormat.ODT,
    "application/vnd.oasis.opendocument.spreadsheet": OfficeFormat.ODS,
    "application/vnd.oasis.opendocument.presentation": OfficeFormat.ODP,
}

ODF_SUFFIX_TO_FORMAT = {
    ".odt": OfficeFormat.ODT,
    ".ods": OfficeFormat.ODS,
    ".odp": OfficeFormat.ODP,
}

WHITESPACE_RE = re.compile(r"[ \t\r\f\v]+")


class OpenDocumentProcessorError(Exception):
    """Base exception for ODF processing."""


class OpenDocumentDependencyError(OpenDocumentProcessorError):
    """Raised when odfpy is unavailable."""


class OpenDocumentNotFoundError(OpenDocumentProcessorError):
    """Raised when an ODF document does not exist."""


class OpenDocumentCorruptedError(OpenDocumentProcessorError):
    """Raised when an ODF package cannot be opened or parsed."""


@dataclass(slots=True)
class ODFDocumentContent(DocumentContent):
    """Shared document content with a convenience ``text`` property."""

    _processor: OpenDocumentProcessor | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @property
    def text(self) -> str:
        """Return normalized plain-text content."""

        if self._processor is not None:
            return self._processor.extract_text()

        if self.paragraphs:
            return "\n".join(
                text
                for text in (
                    paragraph.text_content().strip() for paragraph in self.paragraphs
                )
                if text
            )

        if self.slides:
            parts: list[str] = []
            for index, slide in enumerate(self.slides, start=1):
                if slide.title:
                    title = slide.title.text_content().strip()
                    if title:
                        parts.append(f"Slide {index}: {title}")
                for paragraph in slide.body:
                    text_value = paragraph.text_content().strip()
                    if text_value:
                        parts.append(text_value)
            return "\n".join(parts)

        if self.worksheets:
            parts = []
            for worksheet in self.worksheets:
                parts.append(f"Sheet: {worksheet.name}")
                row_map: dict[int, dict[int, str]] = {}
                for cell in worksheet.iter_cells():
                    row_index, col_index = _cell_reference_to_indexes(cell.reference)
                    row_map.setdefault(row_index, {})[col_index] = (
                        str(cell.value) if cell.value is not None else ""
                    )
                for row_index in sorted(row_map):
                    row = row_map[row_index]
                    max_col = max(row, default=-1)
                    values = [row.get(index, "") for index in range(max_col + 1)]
                    if any(values):
                        parts.append("\t".join(values))
            return "\n".join(parts)

        return ""

    def get_sheet_names(self) -> list[str]:
        """Return worksheet names for spreadsheet documents."""

        return [worksheet.name for worksheet in self.worksheets]

    def extract_sheet(self, name: str | None = None) -> Worksheet:
        """Return a worksheet by name, or the first worksheet if omitted."""

        if not self.worksheets:
            raise ValueError("No worksheets available")
        if name is None:
            return self.worksheets[0]
        for worksheet in self.worksheets:
            if worksheet.name == name:
                return worksheet
        raise ValueError(f"Worksheet not found: {name}")

    def get_slide_count(self) -> int:
        """Return the number of slides for presentation documents."""

        return len(self.slides)

    def extract_slides(self) -> list[Slide]:
        """Return all slides."""

        return list(self.slides)


class OpenDocumentProcessor:
    """High-level ODF processor using shared Office models."""

    def __init__(self, path: str | Path | None = None) -> None:
        self._require_dependency()
        self._document: Any | None = None
        self._path: Path | None = None
        self._format: OfficeFormat | None = None
        self._styles_cache: dict[str, DocumentStyle] | None = None
        self.table_extractor = TableExtractor()
        if path is not None:
            self.load(path)

    # ------------------------------------------------------------------
    # Loading and normalization
    # ------------------------------------------------------------------
    def load(self, path: str | Path) -> OpenDocumentProcessor:
        """Load an ODF document into memory."""

        source = self._validate_source(path)
        self._format = self.detect_format(source)
        try:
            self._document = opendocument.load(str(source))
        except Exception as exc:  # pragma: no cover - dependency/library boundary
            raise OpenDocumentCorruptedError(
                f"Failed to open ODF document: {source}"
            ) from exc

        self._path = source
        self._styles_cache = None
        return self

    def parse(self, path: str | Path | None = None) -> ODFDocumentContent:
        """Parse an ODF document into the shared document model."""

        source = self._coerce_source(path)
        format_name = self._ensure_format(path)
        paragraphs = self.extract_paragraphs(path)
        tables = self.extract_tables(path)
        images = self.extract_images(path)
        metadata = self.get_metadata(path)
        styles = self._load_styles(path)

        if format_name == OfficeFormat.ODT:
            content = ODFDocumentContent(
                format=format_name,
                paragraphs=paragraphs,
                tables=tables,
                images=images,
                metadata=metadata,
                styles=styles,
                document_properties={
                    "paragraph_count": len(paragraphs),
                    "table_count": len(tables),
                    "image_count": len(images),
                },
                sections=[
                    paragraph.text_content()
                    for paragraph in paragraphs
                    if paragraph.is_heading
                ],
                _processor=self,
            )
        elif format_name == OfficeFormat.ODS:
            worksheets = self.extract_worksheets(path)
            table_count = sum(len(worksheet.tables) for worksheet in worksheets)
            content = ODFDocumentContent(
                format=format_name,
                paragraphs=paragraphs,
                tables=tables,
                images=images,
                worksheets=worksheets,
                metadata=metadata,
                styles=styles,
                document_properties={
                    "sheet_count": len(worksheets),
                    "cell_count": sum(len(worksheet.cells) for worksheet in worksheets),
                    "table_count": table_count or len(tables),
                    "image_count": len(images),
                },
                _processor=self,
            )
        elif format_name == OfficeFormat.ODP:
            slides = self.extract_slides(path)
            content = ODFDocumentContent(
                format=format_name,
                paragraphs=paragraphs,
                tables=tables,
                images=images,
                slides=slides,
                metadata=metadata,
                styles=styles,
                document_properties={
                    "slide_count": len(slides),
                    "paragraph_count": len(paragraphs),
                    "table_count": len(tables),
                    "image_count": len(images),
                },
                _processor=self,
            )
        else:  # pragma: no cover - defensive
            raise UnsupportedOfficeFormatError(format_name)

        if source is not None:
            content.resources = self._load_picture_resources(source)
        return content

    # ------------------------------------------------------------------
    # Public extraction API
    # ------------------------------------------------------------------
    def detect_format(self, path: str | Path) -> OfficeFormat:
        """Detect whether a document is ODT, ODS, or ODP."""

        source = self._validate_source(path)
        suffix_format = ODF_SUFFIX_TO_FORMAT.get(source.suffix.lower())
        mimetype_format = self._detect_format_from_mimetype(source)
        archive_format = self._detect_format_from_archive(source)

        for detected in (mimetype_format, archive_format, suffix_format):
            if detected is not None:
                return detected

        raise UnsupportedOfficeFormatError(source.suffix.lower().lstrip("."))

    def detect_type(self, path: str | Path) -> OfficeFormat:
        """Backward-compatible alias for :meth:`detect_format`."""

        return self.detect_format(path)

    def extract_text(self, path: str | Path | None = None) -> str:
        """Extract all visible text in a normalized plain-text form."""

        format_name = self._ensure_format(path)
        if format_name == OfficeFormat.ODT:
            return self._extract_odt_text(path)
        if format_name == OfficeFormat.ODS:
            return self._extract_ods_text(path)
        if format_name == OfficeFormat.ODP:
            return self._extract_odp_text(path)
        raise UnsupportedOfficeFormatError(format_name)

    def extract_paragraphs(self, path: str | Path | None = None) -> list[Paragraph]:
        """Extract structured content as normalized paragraphs."""

        format_name = self._ensure_format(path)
        if format_name == OfficeFormat.ODT:
            return self._extract_odt_paragraphs(path)
        if format_name == OfficeFormat.ODS:
            return self._extract_ods_paragraphs(path)
        if format_name == OfficeFormat.ODP:
            return self._extract_odp_paragraphs(path)
        raise UnsupportedOfficeFormatError(format_name)

    def extract_tables(self, path: str | Path | None = None) -> list[Table]:
        """Extract tables across text, spreadsheet, and presentation ODF files."""

        source = self._require_source(path)
        format_name = self._ensure_format(path)

        if format_name == OfficeFormat.ODT:
            extracted = self.table_extractor.extract_tables(source)
            return [
                self._convert_table(table_model, index)
                for index, table_model in enumerate(extracted, start=1)
            ]

        if format_name == OfficeFormat.ODS:
            extracted = self._extract_ods_tables(path)
            return [
                self._convert_table(table_model, index)
                for index, table_model in enumerate(extracted, start=1)
            ]

        if format_name == OfficeFormat.ODP:
            extracted = self._extract_odp_tables(path)
            return [
                self._convert_table(table_model, index)
                for index, table_model in enumerate(extracted, start=1)
            ]

        raise UnsupportedOfficeFormatError(format_name)

    def extract_images(self, path: str | Path | None = None) -> list[Image]:
        """Extract embedded package images from the ``Pictures/`` folder."""

        source = self._require_source(path)
        image_refs = self._collect_image_references(path)
        media_types = self._read_manifest_media_types(source)
        images: list[Image] = []

        try:
            with zipfile.ZipFile(source) as archive:
                picture_entries = sorted(
                    name
                    for name in archive.namelist()
                    if name.startswith("Pictures/") and not name.endswith("/")
                )

                for entry in picture_entries:
                    try:
                        payload = archive.read(entry)
                    except KeyError:  # pragma: no cover - corrupt archive edge
                        continue

                    reference_data = image_refs.get(entry, [])
                    first_ref = reference_data[0] if reference_data else {}
                    mime_type = (
                        media_types.get(entry)
                        or mimetypes.guess_type(entry)[0]
                        or "application/octet-stream"
                    )
                    properties: dict[str, str | float | bool] = {
                        "path": entry,
                        "reference_count": float(len(reference_data)),
                    }
                    if first_ref.get("slide_index"):
                        try:
                            properties["slide_index"] = float(
                                str(first_ref["slide_index"])
                            )
                        except (TypeError, ValueError):
                            pass
                    if reference_data:
                        frame_names = [
                            ref["frame_name"]
                            for ref in reference_data
                            if isinstance(ref.get("frame_name"), str)
                            and ref["frame_name"]
                        ]
                        if frame_names:
                            properties["frame_names"] = ", ".join(frame_names)

                    images.append(
                        Image(
                            data=payload,
                            mime_type=mime_type,
                            description=self._clean_text(first_ref.get("description")),
                            width=self._safe_float(first_ref.get("width")),
                            height=self._safe_float(first_ref.get("height")),
                            title=self._clean_text(first_ref.get("name"))
                            or Path(entry).name,
                            alternate_text=self._clean_text(
                                first_ref.get("alternate_text")
                            ),
                            properties=properties,
                        )
                    )
        except zipfile.BadZipFile as exc:
            raise OpenDocumentCorruptedError(f"Invalid ODF package: {source}") from exc

        return images

    def get_metadata(self, path: str | Path | None = None) -> Metadata:
        """Extract document metadata and custom properties."""

        document = self._ensure_document(path)
        metadata = Metadata()
        if getattr(document, "meta", None) is None:
            return metadata

        for child in getattr(document.meta, "childNodes", []):
            tag_name = _local_name(getattr(child, "tagName", "")) or _qname_local_name(
                child
            )
            value = self._clean_text(extractText(child))
            if not tag_name:
                continue

            if tag_name == "title" and value:
                metadata.title = value
            elif tag_name == "subject" and value:
                metadata.subject = value
            elif (
                tag_name in {"creator", "initial-creator"}
                and value
                and metadata.author is None
            ):
                metadata.author = value
            elif tag_name == "keyword" and value:
                metadata.keywords.extend(self._split_keywords(value))
            elif tag_name in {"creation-date", "date"} and value:
                parsed = self._parse_datetime(value)
                if tag_name == "creation-date" and parsed is not None:
                    metadata.created_at = parsed
                elif tag_name == "date" and parsed is not None:
                    metadata.modified_at = parsed
            elif tag_name == "printed-by" and value:
                metadata.custom_properties["printed_by"] = value
            elif tag_name == "editing-cycles" and value:
                metadata.custom_properties["editing_cycles"] = value
            elif tag_name == "editing-duration" and value:
                metadata.custom_properties["editing_duration"] = value
            elif tag_name == "generator" and value:
                metadata.custom_properties["generator"] = value
            elif tag_name == "document-statistic":
                statistics = self._extract_document_statistics(child)
                metadata.custom_properties.update(statistics)
            elif tag_name == "user-defined":
                property_name = self._get_attribute(child, "name")
                property_type = self._get_attribute(child, "valuetype")
                if property_name and value:
                    metadata.custom_properties[property_name] = (
                        self._coerce_metadata_value(value, property_type)
                    )

        metadata.keywords = list(dict.fromkeys(metadata.keywords))
        metadata.company = self._first_present(
            metadata.custom_properties,
            ("Company", "company", "Organisation", "organization", "organisation"),
        )
        metadata.category = self._first_present(
            metadata.custom_properties, ("Category", "category")
        )
        return metadata

    def extract_worksheets(self, path: str | Path | None = None) -> list[Worksheet]:
        """Extract Calc worksheets into the shared worksheet model."""

        self._ensure_spreadsheet(path)
        sheets: list[Worksheet] = []
        for sheet_index, sheet_element in enumerate(
            self._sheet_elements(path), start=1
        ):
            name = self._get_attribute(sheet_element, "name") or f"Sheet {sheet_index}"
            worksheet = Worksheet(name=name)
            normalized_table = self._parse_odf_table_element(
                sheet_element,
                source_format="ods",
                source={"sheet_name": name, "sheet_index": sheet_index},
            )
            if normalized_table is not None:
                worksheet.tables.append(
                    self._convert_table(normalized_table, sheet_index)
                )
                self._populate_worksheet_cells(worksheet, normalized_table)
            sheets.append(worksheet)
        return sheets

    def extract_slides(self, path: str | Path | None = None) -> list[Slide]:
        """Extract Impress slides into the shared slide model."""

        presentation = self._ensure_presentation(path)
        all_tables = (
            self.extract_tables(path)
            if self._ensure_format(path) == OfficeFormat.ODP
            else []
        )
        image_map = self._group_slide_images(self.extract_images(path))
        table_map = self._group_slide_tables(all_tables)
        slides: list[Slide] = []

        for slide_index, page in enumerate(
            self._presentation_pages(presentation), start=1
        ):
            title_paragraph: Paragraph | None = None
            body: list[Paragraph] = []
            notes: list[Paragraph] = []

            for frame in self._iter_elements(page, allowed={"frame"}):
                frame_class = self._clean_text(
                    self._get_attribute(frame, "presentationclass")
                ).lower()
                paragraphs = self._paragraphs_from_frame(frame, slide_index)
                if not paragraphs:
                    continue

                if frame_class == "title" or (
                    title_paragraph is None and self._frame_looks_like_title(frame)
                ):
                    title_paragraph = paragraphs[0]
                    body.extend(paragraphs[1:])
                elif frame_class in {"notes", "subtitle-notes"}:
                    notes.extend(paragraphs)
                else:
                    body.extend(paragraphs)

            slides.append(
                Slide(
                    title=title_paragraph,
                    body=body,
                    notes=notes,
                    images=image_map.get(slide_index, []),
                    tables=table_map.get(slide_index, []),
                    layout_name=self._clean_text(
                        self._get_attribute(page, "style-name")
                    )
                    or None,
                    master_slide_name=self._clean_text(
                        self._get_attribute(page, "master-page-name")
                    )
                    or None,
                )
            )

        return slides

    # ------------------------------------------------------------------
    # ODT extraction
    # ------------------------------------------------------------------
    def _extract_odt_text(self, path: str | Path | None = None) -> str:
        body = self._ensure_text_document(path)
        parts: list[str] = []
        for element in self._iter_elements(body, allowed={"h", "p", "table"}):
            tag_name = _qname_local_name(element)
            if tag_name in {"h", "p"}:
                text_value = self._clean_text(self._element_text(element))
                if text_value:
                    parts.append(text_value)
            elif tag_name == "table":
                normalized = self._parse_odf_table_element(
                    element,
                    source_format="odt",
                    source={"path": str(self._require_source(path))},
                )
                if normalized is None:
                    continue
                for row in normalized.rows:
                    row_values = [cell.text for cell in row if not cell.is_placeholder]
                    if any(row_values):
                        parts.append(" | ".join(row_values))
        return "\n\n".join(parts)

    def _extract_odt_paragraphs(
        self, path: str | Path | None = None
    ) -> list[Paragraph]:
        body = self._ensure_text_document(path)
        paragraphs: list[Paragraph] = []
        for index, element in enumerate(
            self._iter_elements(body, allowed={"h", "p"}), start=1
        ):
            text_value = self._clean_text(self._element_text(element))
            if not text_value:
                continue
            tag_name = _qname_local_name(element)
            style_name = self._get_attribute(
                element, "stylename"
            ) or self._get_attribute(element, "style-name")
            heading_level = None
            is_heading = tag_name == "h"
            if is_heading:
                try:
                    heading_level = int(
                        self._get_attribute(element, "outlinelevel") or "1"
                    )
                except ValueError:
                    heading_level = 1

            paragraphs.append(
                Paragraph(
                    runs=[TextRun(text=text_value)],
                    style=self._style_from_name(style_name),
                    paragraph_id=f"odt-p-{index}",
                    is_heading=is_heading,
                    heading_level=heading_level,
                )
            )
        return paragraphs

    # ------------------------------------------------------------------
    # ODS extraction
    # ------------------------------------------------------------------
    def _extract_ods_text(self, path: str | Path | None = None) -> str:
        parts: list[str] = []
        for worksheet in self.extract_worksheets(path):
            parts.append(f"Sheet: {worksheet.name}")
            row_map: dict[int, dict[int, str]] = {}
            for cell in worksheet.iter_cells():
                row_index, col_index = _cell_reference_to_indexes(cell.reference)
                row_map.setdefault(row_index, {})[col_index] = (
                    str(cell.value) if cell.value is not None else ""
                )
            for row_index in sorted(row_map):
                row = row_map[row_index]
                max_col = max(row, default=-1)
                values = [row.get(index, "") for index in range(max_col + 1)]
                if any(value.strip() for value in values):
                    parts.append("\t".join(values))
            parts.append("")
        return "\n".join(parts).strip()

    def _extract_ods_paragraphs(
        self, path: str | Path | None = None
    ) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        for worksheet in self.extract_worksheets(path):
            row_map: dict[int, dict[int, str]] = {}
            for cell in worksheet.iter_cells():
                row_index, col_index = _cell_reference_to_indexes(cell.reference)
                row_map.setdefault(row_index, {})[col_index] = (
                    str(cell.value) if cell.value is not None else ""
                )

            for row_index in sorted(row_map):
                row = row_map[row_index]
                max_col = max(row, default=-1)
                values = [row.get(index, "") for index in range(max_col + 1)]
                cleaned = [value for value in values if value and value.strip()]
                if not cleaned:
                    continue
                paragraphs.append(
                    Paragraph(
                        runs=[TextRun(text="\t".join(values).strip())],
                        style=DocumentStyle(
                            styles={
                                "sheet_name": worksheet.name,
                                "row_index": row_index + 1,
                            }
                        ),
                        paragraph_id=f"{worksheet.name}-row-{row_index + 1}",
                    )
                )
        return paragraphs

    def _extract_ods_tables(
        self, path: str | Path | None = None
    ) -> list[ExtractedTable]:
        tables: list[ExtractedTable] = []
        for sheet_index, sheet_element in enumerate(
            self._sheet_elements(path), start=1
        ):
            sheet_name = (
                self._get_attribute(sheet_element, "name") or f"Sheet {sheet_index}"
            )
            normalized = self._parse_odf_table_element(
                sheet_element,
                source_format="ods",
                source={"sheet_name": sheet_name, "sheet_index": sheet_index},
            )
            if normalized is not None:
                tables.append(normalized)
        return tables

    # ------------------------------------------------------------------
    # ODP extraction
    # ------------------------------------------------------------------
    def _extract_odp_text(self, path: str | Path | None = None) -> str:
        slides = self.extract_slides(path)
        parts: list[str] = []
        for index, slide in enumerate(slides, start=1):
            if slide.title:
                title = slide.title.text_content().strip()
                if title:
                    parts.append(f"Slide {index}: {title}")
            for paragraph in slide.body:
                text_value = paragraph.text_content().strip()
                if text_value:
                    parts.append(text_value)
            for table_model in slide.tables:
                for row in table_model.rows:
                    row_text = [cell.text_content() for cell in row]
                    if any(row_text):
                        parts.append(" | ".join(row_text))
            if slide.notes:
                parts.append("Notes:")
                parts.extend(
                    paragraph.text_content().strip()
                    for paragraph in slide.notes
                    if paragraph.text_content().strip()
                )
            parts.append("")
        return "\n".join(parts).strip()

    def _extract_odp_paragraphs(
        self, path: str | Path | None = None
    ) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        for slide_index, slide in enumerate(self.extract_slides(path), start=1):
            if slide.title:
                title = slide.title
                title.paragraph_id = title.paragraph_id or f"slide-{slide_index}-title"
                title.is_heading = True
                title.heading_level = 1
                paragraphs.append(title)
            for paragraph_index, paragraph in enumerate(slide.body, start=1):
                paragraph.paragraph_id = (
                    paragraph.paragraph_id or f"slide-{slide_index}-p-{paragraph_index}"
                )
                paragraphs.append(paragraph)
            for note_index, paragraph in enumerate(slide.notes, start=1):
                paragraph.paragraph_id = (
                    paragraph.paragraph_id or f"slide-{slide_index}-note-{note_index}"
                )
                paragraph.style.styles.setdefault("notes", True)
                paragraphs.append(paragraph)
        return paragraphs

    def _extract_odp_tables(
        self, path: str | Path | None = None
    ) -> list[ExtractedTable]:
        presentation = self._ensure_presentation(path)
        tables: list[ExtractedTable] = []
        for slide_index, page in enumerate(
            self._presentation_pages(presentation), start=1
        ):
            for table_index, table_element in enumerate(
                self._iter_elements(page, allowed={"table"}), start=1
            ):
                normalized = self._parse_odf_table_element(
                    table_element,
                    source_format="odp",
                    source={"slide_index": slide_index, "table_index": table_index},
                )
                if normalized is not None:
                    normalized.source.setdefault("slide_index", slide_index)
                    tables.append(normalized)
        return tables

    # ------------------------------------------------------------------
    # Shared ODF helpers
    # ------------------------------------------------------------------
    def _parse_odf_table_element(
        self,
        table_element: Any,
        *,
        source_format: str,
        source: dict[str, Any],
    ) -> ExtractedTable | None:
        logical_rows: list[list[ExtractedCell]] = []
        active_rowspans: dict[int, int] = {}

        for row_element in self._direct_children(table_element, allowed={"table-row"}):
            repeat_rows = self._safe_int(
                self._get_attribute(row_element, "numberrowsrepeated"), default=1
            )
            base_row = self._parse_odf_row(row_element, active_rowspans)
            if not base_row and not active_rowspans:
                continue
            for _ in range(max(repeat_rows, 1)):
                row_copy = [self._clone_extracted_cell(cell) for cell in base_row]
                logical_rows.append(row_copy)

        if not logical_rows:
            return None

        style_name = self._get_attribute(
            table_element, "stylename"
        ) or self._get_attribute(table_element, "style-name")
        table_name = self._get_attribute(table_element, "name")
        return ExtractedTable(
            rows=logical_rows,
            headers=[],
            header_row_count=0,
            style={
                "format": source_format,
                "style_name": style_name,
                "table_name": table_name,
            },
            source=source,
        )

    def _parse_odf_row(
        self,
        row_element: Any,
        active_rowspans: dict[int, int],
    ) -> list[ExtractedCell]:
        row: list[ExtractedCell] = []
        column_index = 0

        while active_rowspans.get(column_index, 0) > 0:
            row.append(ExtractedCell(text="", is_placeholder=True))
            active_rowspans[column_index] -= 1
            if active_rowspans[column_index] <= 0:
                active_rowspans.pop(column_index, None)
            column_index += 1

        for cell_element in self._direct_children(
            row_element, allowed={"table-cell", "covered-table-cell"}
        ):
            while active_rowspans.get(column_index, 0) > 0:
                row.append(ExtractedCell(text="", is_placeholder=True))
                active_rowspans[column_index] -= 1
                if active_rowspans[column_index] <= 0:
                    active_rowspans.pop(column_index, None)
                column_index += 1

            repeated = self._safe_int(
                self._get_attribute(cell_element, "numbercolumnsrepeated"), default=1
            )
            rowspan = self._safe_int(
                self._get_attribute(cell_element, "numberrowsspanned"), default=1
            )
            colspan = self._safe_int(
                self._get_attribute(cell_element, "numbercolumnsspanned"), default=1
            )
            is_covered = _qname_local_name(cell_element) == "covered-table-cell"
            text_value = self._clean_text(self._element_text(cell_element))
            style_name = self._get_attribute(cell_element, "stylename")
            value_type = self._get_attribute(cell_element, "valuetype")
            formula = self._get_attribute(cell_element, "formula")
            raw_value = self._extract_table_cell_value(
                cell_element, value_type, text_value
            )

            for _ in range(max(repeated, 1)):
                cell = ExtractedCell(
                    value=raw_value,
                    text=text_value,
                    data_type=value_type or ("empty" if not text_value else "string"),
                    rowspan=1 if is_covered else max(rowspan, 1),
                    colspan=1 if is_covered else max(colspan, 1),
                    is_placeholder=is_covered,
                    formula=formula,
                    style={"style_name": style_name} if style_name else {},
                    source={},
                )
                row.append(cell)

                if not is_covered and cell.rowspan > 1:
                    for offset in range(max(cell.colspan, 1)):
                        active_rowspans[column_index + offset] = cell.rowspan - 1

                column_index += 1

        while active_rowspans.get(column_index, 0) > 0:
            row.append(ExtractedCell(text="", is_placeholder=True))
            active_rowspans[column_index] -= 1
            if active_rowspans[column_index] <= 0:
                active_rowspans.pop(column_index, None)
            column_index += 1

        return row

    def _paragraphs_from_frame(self, frame: Any, slide_index: int) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        for paragraph_index, paragraph_element in enumerate(
            self._iter_elements(frame, allowed={"p", "h"}), start=1
        ):
            text_value = self._clean_text(self._element_text(paragraph_element))
            if not text_value:
                continue
            tag_name = _qname_local_name(paragraph_element)
            style_name = self._get_attribute(paragraph_element, "stylename")
            heading_level = None
            is_heading = tag_name == "h"
            if is_heading:
                heading_level = self._safe_int(
                    self._get_attribute(paragraph_element, "outlinelevel"), default=1
                )

            paragraphs.append(
                Paragraph(
                    runs=[TextRun(text=text_value)],
                    style=self._style_from_name(style_name),
                    paragraph_id=f"slide-{slide_index}-frame-p-{paragraph_index}",
                    is_heading=is_heading,
                    heading_level=heading_level,
                )
            )
        return paragraphs

    def _collect_image_references(
        self, path: str | Path | None = None
    ) -> dict[str, list[dict[str, str]]]:
        document = self._ensure_document(path)
        references: dict[str, list[dict[str, str]]] = {}

        current_slide = 0
        for element in self._iter_elements(
            document, allowed={"page", "frame", "image"}
        ):
            tag_name = _qname_local_name(element)
            if tag_name == "page":
                current_slide += 1
                continue
            if tag_name != "image":
                continue

            href = self._get_attribute(element, "href")
            if not href:
                continue

            frame = getattr(element, "parentNode", None)
            reference = {
                "name": self._clean_text(self._get_attribute(frame, "name")),
                "frame_name": self._clean_text(self._get_attribute(frame, "name")),
                "description": self._clean_text(
                    self._get_attribute(frame, "description")
                ),
                "alternate_text": self._clean_text(self._get_attribute(frame, "title")),
                "width": self._clean_text(self._get_attribute(frame, "width")),
                "height": self._clean_text(self._get_attribute(frame, "height")),
            }
            if current_slide:
                reference["slide_index"] = str(current_slide)
            references.setdefault(href, []).append(reference)

        return references

    def _load_styles(self, path: str | Path | None = None) -> dict[str, DocumentStyle]:
        if path is not None:
            self._ensure_document(path)
        if self._styles_cache is not None:
            return dict(self._styles_cache)

        document = self._ensure_document(path)
        styles_by_name: dict[str, DocumentStyle] = {}

        for container_name in ("styles", "automaticstyles", "masterstyles"):
            container = getattr(document, container_name, None)
            if container is None:
                continue
            for style_element in self._iter_elements(
                container, allowed={"style", "default-style"}
            ):
                style_name = self._get_attribute(
                    style_element, "name"
                ) or self._get_attribute(style_element, "family")
                if not style_name:
                    continue

                properties: dict[str, str | float | bool] = {}
                for child in getattr(style_element, "childNodes", []):
                    if not hasattr(child, "attributes"):
                        continue
                    for attribute_name, attribute_value in getattr(
                        child, "attributes", {}
                    ).items():
                        properties[str(attribute_name)] = str(attribute_value)

                style_model = DocumentStyle(styles=properties)
                style_model.font_family = str(
                    properties.get("fontname", style_model.font_family)
                )
                style_model.alignment = str(
                    properties.get("textalign", style_model.alignment)
                )
                style_model.bold = (
                    str(properties.get("fontweight", "")).lower() == "bold"
                )
                style_model.italic = (
                    str(properties.get("fontstyle", "")).lower() == "italic"
                )
                style_model.underline = (
                    "underline"
                    in str(properties.get("textunderline-style", "")).lower()
                )
                style_model.text_color = str(
                    properties.get("color", style_model.text_color)
                )
                style_model.background_color = str(
                    properties.get("background-color", style_model.background_color)
                )
                font_size = self._parse_length(properties.get("fontsize"))
                if font_size is not None:
                    style_model.font_size = font_size

                styles_by_name[style_name] = style_model

        self._styles_cache = styles_by_name
        return dict(styles_by_name)

    def _style_from_name(self, style_name: str | None) -> DocumentStyle:
        style_map = self._load_styles()
        base = style_map.get(style_name or "")
        if base is None:
            return DocumentStyle(
                styles={"style_name": style_name} if style_name else {}
            )
        return DocumentStyle(
            font_family=base.font_family,
            font_size=base.font_size,
            bold=base.bold,
            italic=base.italic,
            underline=base.underline,
            strikethrough=base.strikethrough,
            text_color=base.text_color,
            background_color=base.background_color,
            alignment=base.alignment,
            line_spacing=base.line_spacing,
            spacing_before=base.spacing_before,
            spacing_after=base.spacing_after,
            indentation_left=base.indentation_left,
            indentation_right=base.indentation_right,
            indentation_first_line=base.indentation_first_line,
            styles=dict(base.styles),
        )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
    def _convert_table(self, table_model: ExtractedTable, index: int) -> Table:
        rows: list[list[TableCell]] = []
        cell_grid: dict[str, TableCell] = {}

        for row_index, row in enumerate(table_model.rows):
            converted_row: list[TableCell] = []
            for col_index, cell in enumerate(row):
                cell_id = f"table-{index}-r{row_index + 1}-c{col_index + 1}"
                converted_cell = self._convert_table_cell(cell, cell_id)
                converted_row.append(converted_cell)
                cell_grid[cell_id] = converted_cell
            rows.append(converted_row)

        return Table(
            rows=rows,
            alignment="left",
            style=DocumentStyle(
                styles={**dict(table_model.style), **dict(table_model.source)}
            ),
            has_header_row=table_model.header_row_count > 0,
            cell_grid=cell_grid,
            table_id=f"table-{index}",
        )

    def _convert_table_cell(self, cell: ExtractedCell, cell_id: str) -> TableCell:
        paragraph = Paragraph(
            runs=[TextRun(text=cell.text)],
            style=DocumentStyle(styles={"source_data_type": cell.data_type}),
        )
        shading_color = (
            cell.style.get("background_color") if isinstance(cell.style, dict) else None
        )
        return TableCell(
            paragraphs=[paragraph] if cell.text else [],
            rowspan=cell.rowspan,
            colspan=cell.colspan,
            style=DocumentStyle(styles=dict(cell.style)),
            shading_color=str(shading_color) if shading_color else None,
            cell_id=cell_id,
        )

    def _populate_worksheet_cells(
        self, worksheet: Worksheet, normalized_table: ExtractedTable
    ) -> None:
        for row_index, row in enumerate(normalized_table.rows, start=1):
            for col_index, cell in enumerate(row, start=1):
                if cell.is_placeholder and not cell.text:
                    continue
                reference = _indexes_to_cell_reference(row_index - 1, col_index - 1)
                worksheet.set_cell(
                    Cell(
                        reference=reference,
                        value=(
                            cell.value
                            if cell.value is not None
                            else (cell.text or None)
                        ),
                        formula=cell.formula,
                        style=DocumentStyle(styles=dict(cell.style)),
                        merged=cell.rowspan > 1 or cell.colspan > 1,
                        merge_range=(
                            _merge_range(
                                reference,
                                row_index - 1,
                                col_index - 1,
                                cell.rowspan,
                                cell.colspan,
                            )
                            if cell.rowspan > 1 or cell.colspan > 1
                            else None
                        ),
                    )
                )

    def _group_slide_images(self, images: Sequence[Image]) -> dict[int, list[Image]]:
        grouped: dict[int, list[Image]] = {}
        for image in images:
            slide_index_value = image.properties.get("slide_index")
            if slide_index_value is None:
                continue
            try:
                slide_index = int(float(str(slide_index_value)))
            except (TypeError, ValueError):
                continue
            grouped.setdefault(slide_index, []).append(image)
        return grouped

    def _group_slide_tables(self, tables: Sequence[Table]) -> dict[int, list[Table]]:
        grouped: dict[int, list[Table]] = {}
        for table_model in tables:
            slide_index_value = table_model.style.styles.get("slide_index")
            if slide_index_value is None:
                continue
            try:
                slide_index = int(float(str(slide_index_value)))
            except (TypeError, ValueError):
                continue
            grouped.setdefault(slide_index, []).append(table_model)
        return grouped

    # ------------------------------------------------------------------
    # Package and XML helpers
    # ------------------------------------------------------------------
    def _detect_format_from_mimetype(self, source: Path) -> OfficeFormat | None:
        try:
            with zipfile.ZipFile(source) as archive:
                if "mimetype" not in archive.namelist():
                    return None
                mimetype_value = (
                    archive.read("mimetype").decode("utf-8", errors="ignore").strip()
                )
        except Exception:
            return None
        return ODF_MIMETYPE_TO_FORMAT.get(mimetype_value)

    def _detect_format_from_archive(self, source: Path) -> OfficeFormat | None:
        try:
            with zipfile.ZipFile(source) as archive:
                if "content.xml" not in archive.namelist():
                    return None
                root = ET.fromstring(archive.read("content.xml"))
        except Exception:
            return None

        body = root.find("office:body", ODF_NS)
        if body is None:
            return None
        for child in body:
            local_name = _local_name(child.tag)
            if local_name == "text":
                return OfficeFormat.ODT
            if local_name == "spreadsheet":
                return OfficeFormat.ODS
            if local_name == "presentation":
                return OfficeFormat.ODP
        return None

    def _read_manifest_media_types(self, source: Path) -> dict[str, str]:
        try:
            with zipfile.ZipFile(source) as archive:
                manifest_xml = archive.read("META-INF/manifest.xml")
        except Exception:
            return {}

        result: dict[str, str] = {}
        try:
            root = ET.fromstring(manifest_xml)
        except ET.ParseError:
            return result

        for file_entry in root.findall(".//manifest:file-entry", ODF_NS):
            full_path = file_entry.get(f"{{{ODF_NS['manifest']}}}full-path")
            media_type = file_entry.get(f"{{{ODF_NS['manifest']}}}media-type")
            if full_path and media_type:
                result[full_path] = media_type
        return result

    def _load_picture_resources(self, source: Path) -> dict[str, bytes]:
        try:
            with zipfile.ZipFile(source) as archive:
                return {
                    name: archive.read(name)
                    for name in archive.namelist()
                    if name.startswith("Pictures/") and not name.endswith("/")
                }
        except Exception:
            return {}

    def _extract_document_statistics(self, element: Any) -> dict[str, str | int]:
        stats: dict[str, str | int] = {}
        attributes = getattr(element, "attributes", {}) or {}
        for attribute_name, attribute_value in attributes.items():
            name = str(attribute_name)
            value = str(attribute_value)
            if value.isdigit():
                stats[name] = int(value)
            else:
                stats[name] = value
        return stats

    def _extract_table_cell_value(
        self, element: Any, value_type: str | None, text_value: str
    ) -> Any:
        if value_type in {"float", "percentage", "currency"}:
            raw_value = self._get_attribute(element, "value")
            try:
                return float(raw_value) if raw_value is not None else None
            except ValueError:
                return text_value or raw_value
        if value_type == "boolean":
            raw_value = self._get_attribute(element, "booleanvalue")
            if raw_value is None:
                return None
            return str(raw_value).strip().lower() == "true"
        if value_type == "date":
            raw_value = self._get_attribute(element, "datevalue")
            return self._parse_datetime(raw_value) or raw_value
        if value_type == "time":
            return self._get_attribute(element, "timevalue") or text_value
        return text_value

    def _coerce_metadata_value(
        self, value: str, value_type: str | None
    ) -> str | int | float | bool | datetime:
        normalized = value.strip()
        if value_type == "boolean":
            return normalized.lower() in {"true", "1", "yes"}
        if value_type in {"float", "percentage", "currency"}:
            try:
                return float(normalized)
            except ValueError:
                return normalized
        parsed = self._parse_datetime(normalized)
        if parsed is not None:
            return parsed
        if normalized.isdigit():
            return int(normalized)
        return normalized

    def _sheet_elements(self, path: str | Path | None = None) -> list[Any]:
        spreadsheet = self._ensure_spreadsheet(path)
        return list(self._direct_children(spreadsheet, allowed={"table"}))

    def _presentation_pages(self, presentation: Any) -> list[Any]:
        return list(self._direct_children(presentation, allowed={"page"}))

    def _ensure_text_document(self, path: str | Path | None = None) -> Any:
        document = self._ensure_document(path)
        body = getattr(document, "text", None)
        if body is None or self._ensure_format(path) != OfficeFormat.ODT:
            raise DocumentValidationError("Loaded document is not an ODT text document")
        return body

    def _ensure_spreadsheet(self, path: str | Path | None = None) -> Any:
        document = self._ensure_document(path)
        spreadsheet = getattr(document, "spreadsheet", None)
        if spreadsheet is None or self._ensure_format(path) != OfficeFormat.ODS:
            raise DocumentValidationError("Loaded document is not an ODS spreadsheet")
        return spreadsheet

    def _ensure_presentation(self, path: str | Path | None = None) -> Any:
        document = self._ensure_document(path)
        presentation = getattr(document, "presentation", None)
        if presentation is None or self._ensure_format(path) != OfficeFormat.ODP:
            raise DocumentValidationError("Loaded document is not an ODP presentation")
        return presentation

    def _ensure_document(self, path: str | Path | None = None) -> Any:
        if path is not None:
            requested = Path(path).expanduser()
            if self._path != requested:
                self.load(requested)
        if self._document is None:
            raise DocumentValidationError("No ODF document loaded")
        return self._document

    def _ensure_format(self, path: str | Path | None = None) -> OfficeFormat:
        if path is not None:
            requested = Path(path).expanduser()
            if self._path != requested or self._format is None:
                self.load(requested)
        if self._format is None:
            raise DocumentValidationError("No ODF document loaded")
        return self._format

    def _coerce_source(self, path: str | Path | None = None) -> Path | None:
        if path is not None:
            return Path(path).expanduser()
        return self._path

    def _require_source(self, path: str | Path | None = None) -> Path:
        source = self._coerce_source(path)
        if source is None:
            raise DocumentValidationError("No ODF source path available")
        return self._validate_source(source)

    def _validate_source(self, path: str | Path) -> Path:
        source = Path(path).expanduser()
        if not source.exists():
            raise OpenDocumentNotFoundError(f"File not found: {source}")
        if not source.is_file():
            raise DocumentValidationError("Expected a file path", details=str(source))
        return source

    def _require_dependency(self) -> None:
        if not ODF_AVAILABLE:
            raise OpenDocumentDependencyError(
                "odfpy is required for OpenDocument processing. Install with: pip install odfpy"
            )

    def _iter_elements(self, root: Any, *, allowed: set[str]) -> Iterator[Any]:
        for child in getattr(root, "childNodes", []):
            local_name = _qname_local_name(child)
            if local_name in allowed:
                yield child
            yield from self._iter_elements(child, allowed=allowed)

    def _direct_children(self, root: Any, *, allowed: set[str]) -> Iterator[Any]:
        for child in getattr(root, "childNodes", []):
            if _qname_local_name(child) in allowed:
                yield child

    def _element_text(self, element: Any) -> str:
        parts: list[str] = []

        for child in getattr(element, "childNodes", []):
            local_name = _qname_local_name(child)
            if local_name == "tab":
                parts.append("\t")
            elif local_name in {"line-break", "soft-page-break"}:
                parts.append("\n")
            elif local_name == "s":
                repeat = self._safe_int(self._get_attribute(child, "c"), default=1)
                parts.append(" " * max(repeat, 1))
            elif hasattr(child, "data"):
                parts.append(str(child.data))
            else:
                parts.append(self._element_text(child))

        if not parts:
            return extractText(element)
        return "".join(parts)

    def _frame_looks_like_title(self, frame: Any) -> bool:
        frame_name = self._clean_text(self._get_attribute(frame, "name")).lower()
        return "title" in frame_name if frame_name else False

    def _get_attribute(self, element: Any, name: str) -> str | None:
        if element is None or not hasattr(element, "getAttribute"):
            return None

        candidates = (
            name,
            name.replace("-", ""),
            name.replace("-", "_"),
            name.replace("_", ""),
            name.replace("_", "-"),
        )
        for candidate in candidates:
            try:
                value = element.getAttribute(candidate)
            except Exception:
                continue
            if value not in (None, ""):
                return str(value)
        return None

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        normalized = value.strip().replace("Z", "+00:00")
        for candidate in (normalized, normalized.split("T")[0]):
            try:
                return datetime.fromisoformat(candidate)
            except ValueError:
                continue
        return None

    def _parse_length(self, value: Any) -> float | None:
        if value is None:
            return None
        text_value = str(value).strip()
        match = re.match(r"^\s*([+-]?\d+(?:\.\d+)?)([a-zA-Z%]*)\s*$", text_value)
        if not match:
            return None

        number = float(match.group(1))
        unit = match.group(2).lower()
        if unit in {"", "pt"}:
            return number
        if unit == "in":
            return number * 72.0
        if unit == "cm":
            return number * 28.3464567
        if unit == "mm":
            return number * 2.83464567
        if unit == "pc":
            return number * 12.0
        if unit == "px":
            return number * 0.75
        return number

    def _safe_float(self, value: Any) -> float | None:
        parsed = self._parse_length(value)
        if parsed is not None:
            return parsed
        try:
            return float(str(value))
        except (TypeError, ValueError):
            return None

    def _safe_int(self, value: Any, *, default: int = 0) -> int:
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return default

    def _split_keywords(self, value: str | None) -> list[str]:
        if not value:
            return []
        separators = (";", ",")
        parts = [value]
        for separator in separators:
            if separator in value:
                parts = [chunk for item in parts for chunk in item.split(separator)]
        return [chunk.strip() for chunk in parts if chunk and chunk.strip()]

    def _clean_text(self, value: Any) -> str:
        if value is None:
            return ""
        text_value = str(value).replace("\xa0", " ")
        lines = [
            WHITESPACE_RE.sub(" ", line).strip() for line in text_value.splitlines()
        ]
        return "\n".join(line for line in lines if line)

    def _first_present(
        self,
        values: dict[str, str | int | float | bool | datetime],
        keys: Iterable[str],
    ) -> str | None:
        for key in keys:
            value = values.get(key)
            if value is None:
                continue
            cleaned = self._clean_text(value)
            if cleaned:
                return cleaned
        return None

    def _clone_extracted_cell(self, cell: ExtractedCell) -> ExtractedCell:
        return ExtractedCell(
            value=cell.value,
            text=cell.text,
            data_type=cell.data_type,
            rowspan=cell.rowspan,
            colspan=cell.colspan,
            is_header=cell.is_header,
            is_placeholder=cell.is_placeholder,
            formula=cell.formula,
            style=dict(cell.style),
            source=dict(cell.source),
        )


def _qname_local_name(element: Any) -> str:
    """Return the local qname part for an odfpy element."""

    qname = getattr(element, "qname", None)
    if qname is None:
        return ""
    if isinstance(qname, tuple) and len(qname) == 2:
        return str(qname[1])
    return str(qname)


def _local_name(tag: str) -> str:
    """Return the XML local-name of an ElementTree tag."""

    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _indexes_to_cell_reference(row_index: int, col_index: int) -> str:
    """Convert zero-based row/column indexes to an A1-style reference."""

    column = col_index + 1
    letters = ""
    while column > 0:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"{letters}{row_index + 1}"


def _cell_reference_to_indexes(reference: str) -> tuple[int, int]:
    """Convert an A1-style reference to zero-based indexes."""

    letters = "".join(character for character in reference if character.isalpha())
    numbers = "".join(character for character in reference if character.isdigit())
    column = 0
    for letter in letters.upper():
        column = (column * 26) + (ord(letter) - 64)
    return int(numbers) - 1, column - 1


def _merge_range(
    reference: str, row_index: int, col_index: int, rowspan: int, colspan: int
) -> str:
    """Build an A1 merge range from a top-left reference and span lengths."""

    if rowspan <= 1 and colspan <= 1:
        return reference
    end_reference = _indexes_to_cell_reference(
        row_index + rowspan - 1, col_index + colspan - 1
    )
    return f"{reference}:{end_reference}"
