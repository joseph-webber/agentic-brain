# SPDX-License-Identifier: Apache-2.0

"""Tests for office table models and extraction-oriented structures."""

from __future__ import annotations


def test_table_cell_can_store_multiple_paragraphs(office_modules, sample_paragraph) -> None:
    second = office_modules.models.Paragraph(
        runs=[office_modules.models.TextRun(text="Second line")]
    )
    cell = office_modules.models.TableCell(paragraphs=[sample_paragraph, second])
    assert [para.runs[0].text for para in cell.paragraphs] == [
        "Hello office",
        "Second line",
    ]


def test_table_cell_supports_row_and_column_spans(office_modules) -> None:
    cell = office_modules.models.TableCell(rowspan=3, colspan=2, width=120.0, height=44.0)
    assert cell.rowspan == 3
    assert cell.colspan == 2
    assert cell.width == 120.0
    assert cell.height == 44.0


def test_table_captions_preserve_order(sample_table, sample_paragraph) -> None:
    sample_table.captions.append(sample_paragraph)
    assert len(sample_table.captions) == 2
    assert sample_table.captions[0].paragraph_id == "p-1"


def test_table_cell_grid_allows_direct_addressing(sample_table) -> None:
    assert "A1" in sample_table.cell_grid
    assert sample_table.cell_grid["A1"].colspan == 2


def test_table_header_and_total_row_flags_can_be_combined(office_modules) -> None:
    table = office_modules.models.Table(has_header_row=True, has_total_row=True)
    assert table.has_header_row is True
    assert table.has_total_row is True


def test_worksheet_can_embed_table_objects(office_modules, sample_table) -> None:
    worksheet = office_modules.models.Worksheet(name="Summary", tables=[sample_table])
    assert worksheet.tables[0].has_header_row is True


def test_worksheet_set_and_get_cell_supports_table_extraction(office_modules) -> None:
    worksheet = office_modules.models.Worksheet(name="Sheet1")
    cell = office_modules.models.Cell(reference="A1", value="Header")
    worksheet.set_cell(cell)
    assert worksheet.get_cell("A1") is cell
    assert worksheet.get_cell("B1") is None


def test_worksheet_iter_cells_returns_inserted_cells(office_modules) -> None:
    worksheet = office_modules.models.Worksheet(name="Sheet1")
    worksheet.set_cell(office_modules.models.Cell(reference="A1", value=1))
    worksheet.set_cell(office_modules.models.Cell(reference="B1", value=2))
    assert [cell.reference for cell in worksheet.iter_cells()] == ["A1", "B1"]


def test_spreadsheet_cell_merge_metadata_supports_table_regions(office_modules) -> None:
    cell = office_modules.models.Cell(
        reference="B2",
        merged=True,
        merge_range="B2:C4",
        value="Merged block",
    )
    assert cell.merged is True
    assert cell.merge_range == "B2:C4"


def test_table_style_is_separate_from_cell_style(office_modules) -> None:
    table_style = office_modules.models.DocumentStyle(alignment="center")
    cell_style = office_modules.models.DocumentStyle(alignment="right")
    cell = office_modules.models.TableCell(style=cell_style)
    table = office_modules.models.Table(rows=[[cell]], style=table_style)
    assert table.style.alignment == "center"
    assert table.rows[0][0].style.alignment == "right"


def test_document_content_can_collect_tables_from_multiple_containers(
    office_modules, sample_table, sample_paragraph
) -> None:
    slide = office_modules.models.Slide(body=[sample_paragraph], tables=[sample_table])
    worksheet = office_modules.models.Worksheet(name="Data", tables=[sample_table])
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.XLSX,
        tables=[sample_table],
        slides=[slide],
        worksheets=[worksheet],
    )
    assert len(document.tables) == 1
    assert len(document.slides[0].tables) == 1
    assert len(document.worksheets[0].tables) == 1
