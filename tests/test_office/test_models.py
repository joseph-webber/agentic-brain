# SPDX-License-Identifier: Apache-2.0

"""Tests for office document data models."""

from __future__ import annotations

from datetime import datetime

import pytest


@pytest.mark.parametrize(
    ("member_name", "value"),
    [
        ("DOCX", "docx"),
        ("XLSX", "xlsx"),
        ("PPTX", "pptx"),
        ("PAGES", "pages"),
        ("NUMBERS", "numbers"),
        ("KEYNOTE", "keynote"),
        ("ODT", "odt"),
        ("ODS", "ods"),
        ("ODP", "odp"),
        ("RTF", "rtf"),
    ],
)
def test_office_format_members(office_modules, member_name: str, value: str) -> None:
    assert getattr(office_modules.models.OfficeFormat, member_name).value == value


def test_document_style_defaults(office_modules) -> None:
    style = office_modules.models.DocumentStyle()
    assert style.font_family == "Calibri"
    assert style.font_size == 12.0
    assert style.alignment == "left"
    assert style.text_color == "#000000"
    assert style.background_color == "#FFFFFF"
    assert style.styles == {}


def test_document_style_mutable_defaults_are_isolated(office_modules) -> None:
    first = office_modules.models.DocumentStyle()
    second = office_modules.models.DocumentStyle()
    first.styles["theme"] = "dark"
    assert second.styles == {}


def test_metadata_defaults(office_modules) -> None:
    metadata = office_modules.models.Metadata()
    assert metadata.title is None
    assert metadata.keywords == []
    assert metadata.custom_properties == {}


def test_metadata_mutable_defaults_are_isolated(office_modules) -> None:
    first = office_modules.models.Metadata()
    second = office_modules.models.Metadata()
    first.keywords.append("office")
    first.custom_properties["pages"] = 3
    assert second.keywords == []
    assert second.custom_properties == {}


def test_text_run_defaults(office_modules) -> None:
    run = office_modules.models.TextRun(text="hello")
    assert run.text == "hello"
    assert run.language is None
    assert run.hyperlink is None
    assert run.alternate_text is None


def test_paragraph_defaults(office_modules) -> None:
    paragraph = office_modules.models.Paragraph()
    assert paragraph.runs == []
    assert paragraph.comments == []
    assert paragraph.is_heading is False
    assert paragraph.heading_level is None


def test_paragraph_comment_list_is_isolated(office_modules) -> None:
    comment = office_modules.models.Comment(author="A", text="note")
    first = office_modules.models.Paragraph(comments=[comment])
    second = office_modules.models.Paragraph()
    assert len(first.comments) == 1
    assert second.comments == []


def test_table_cell_defaults(office_modules) -> None:
    cell = office_modules.models.TableCell()
    assert cell.paragraphs == []
    assert cell.rowspan == 1
    assert cell.colspan == 1
    assert cell.borders == {}


def test_table_defaults(office_modules) -> None:
    table = office_modules.models.Table()
    assert table.rows == []
    assert table.alignment == "left"
    assert table.has_header_row is False
    assert table.has_total_row is False
    assert table.cell_grid == {}
    assert table.captions == []


def test_table_mutable_defaults_are_isolated(office_modules) -> None:
    first = office_modules.models.Table()
    second = office_modules.models.Table()
    first.cell_grid["A1"] = office_modules.models.TableCell()
    assert second.cell_grid == {}


def test_image_defaults(office_modules) -> None:
    image = office_modules.models.Image(data=b"img", mime_type="image/png")
    assert image.description is None
    assert image.position == {}
    assert image.properties == {}


def test_shape_defaults(office_modules) -> None:
    shape = office_modules.models.Shape(shape_type="rectangle", path=[{"x": 1.0}])
    assert shape.shape_type == "rectangle"
    assert shape.path == [{"x": 1.0}]
    assert shape.stroke_width == 1.0
    assert shape.properties == {}


def test_chart_defaults(office_modules) -> None:
    chart = office_modules.models.Chart(chart_type="bar")
    assert chart.chart_type == "bar"
    assert chart.series == []
    assert chart.categories == []
    assert chart.legend == {}
    assert chart.position == {}


def test_comment_defaults(office_modules) -> None:
    comment = office_modules.models.Comment(author="Alice", text="Review")
    assert comment.author == "Alice"
    assert comment.text == "Review"
    assert isinstance(comment.created_at, datetime)
    assert comment.resolved is False
    assert comment.replies == []
    assert comment.metadata == {}


def test_comment_replies_are_isolated(office_modules) -> None:
    first = office_modules.models.Comment(author="A", text="one")
    second = office_modules.models.Comment(author="B", text="two")
    reply = office_modules.models.Comment(author="C", text="reply")
    first.replies.append(reply)
    assert second.replies == []


def test_cell_defaults(office_modules) -> None:
    cell = office_modules.models.Cell(reference="A1")
    assert cell.reference == "A1"
    assert cell.value is None
    assert cell.formula is None
    assert cell.comment is None
    assert cell.data_validation == {}
    assert cell.merged is False


def test_worksheet_defaults(office_modules) -> None:
    worksheet = office_modules.models.Worksheet(name="Sheet1")
    assert worksheet.name == "Sheet1"
    assert worksheet.cells == {}
    assert worksheet.column_widths == {}
    assert worksheet.row_heights == {}
    assert worksheet.charts == []
    assert worksheet.tables == []


def test_slide_defaults(office_modules) -> None:
    slide = office_modules.models.Slide()
    assert slide.title is None
    assert slide.body == []
    assert slide.notes == []
    assert slide.images == []
    assert slide.shapes == []
    assert slide.tables == []
    assert slide.charts == []


def test_chart_add_series_appends_series_data(office_modules) -> None:
    chart = office_modules.models.Chart(chart_type="bar")
    chart.add_series("Revenue", [1.0, 2.0], colors=["#111111", "#222222"])
    assert chart.series == [
        {"name": "Revenue", "values": [1.0, 2.0], "colors": ["#111111", "#222222"]}
    ]


def test_comment_methods_update_state(office_modules) -> None:
    comment = office_modules.models.Comment(author="Alice", text="Review")
    reply = office_modules.models.Comment(author="Bob", text="Done")
    comment.add_reply(reply)
    comment.mark_resolved()
    assert comment.replies == [reply]
    assert comment.resolved is True


def test_document_content_defaults(office_modules) -> None:
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.DOCX
    )
    assert document.paragraphs == []
    assert document.tables == []
    assert document.images == []
    assert document.shapes == []
    assert document.slides == []
    assert document.worksheets == []
    assert document.charts == []
    assert document.comments == []
    assert document.styles == {}
    assert document.document_properties == {}
    assert document.resources == {}


def test_document_content_mutable_defaults_are_isolated(office_modules) -> None:
    first = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.DOCX
    )
    second = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.DOCX
    )
    first.resources["thumb.png"] = b"data"
    assert second.resources == {}


def test_document_content_can_aggregate_nested_elements(
    office_modules, sample_image, sample_paragraph, sample_table
) -> None:
    worksheet = office_modules.models.Worksheet(name="Data")
    slide = office_modules.models.Slide(body=[sample_paragraph], images=[sample_image])
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.PPTX,
        paragraphs=[sample_paragraph],
        tables=[sample_table],
        images=[sample_image],
        slides=[slide],
        worksheets=[worksheet],
        comments=[office_modules.models.Comment(author="A", text="Looks good")],
        styles={"Heading1": sample_paragraph.style},
        document_properties={"template": "corporate"},
        resources={"cover.png": b"binary"},
    )
    assert document.format == office_modules.models.OfficeFormat.PPTX
    assert document.slides[0].images[0].alternate_text == "Quarterly revenue chart"
    assert document.tables[0].has_header_row is True
    assert document.styles["Heading1"].bold is True
