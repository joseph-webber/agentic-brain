"""Accessibility-oriented tests for office document structures."""

from __future__ import annotations

import pytest


def test_text_run_can_carry_language_and_alternate_text(office_modules) -> None:
    run = office_modules.models.TextRun(
        text="Bonjour",
        language="fr",
        alternate_text="French greeting",
        hyperlink="https://example.com",
    )
    assert run.language == "fr"
    assert run.alternate_text == "French greeting"
    assert run.hyperlink == "https://example.com"


def test_paragraph_heading_semantics_are_preserved(sample_paragraph) -> None:
    assert sample_paragraph.is_heading is True
    assert sample_paragraph.heading_level == 1


def test_image_alternate_text_is_available_for_screen_readers(sample_image) -> None:
    assert sample_image.alternate_text == "Quarterly revenue chart"
    assert sample_image.description == "Accessible chart image"


def test_table_header_flag_supports_accessible_tables(sample_table) -> None:
    assert sample_table.has_header_row is True


def test_slide_notes_can_store_presenter_accessibility_context(
    office_modules, sample_paragraph
) -> None:
    slide = office_modules.models.Slide(notes=[sample_paragraph])
    assert slide.notes[0].runs[0].text == "Hello office"


def test_comment_metadata_can_store_accessibility_audit_data(office_modules) -> None:
    comment = office_modules.models.Comment(
        author="Auditor",
        text="Add alt text",
        metadata={"severity": "high", "wcag": "1.1.1"},
    )
    assert comment.metadata["wcag"] == "1.1.1"


def test_chart_titles_support_audio_summaries(office_modules) -> None:
    chart = office_modules.models.Chart(
        chart_type="bar",
        title="Q1 Sales",
        categories=["Jan", "Feb", "Mar"],
    )
    assert chart.title == "Q1 Sales"
    assert chart.categories == ["Jan", "Feb", "Mar"]


@pytest.mark.parametrize(
    "document_format",
    ["DOCX", "PPTX", "PAGES", "KEYNOTE", "RTF"],
)
def test_document_content_supports_accessible_formats(office_modules, document_format: str) -> None:
    document = office_modules.models.DocumentContent(
        format=getattr(office_modules.models.OfficeFormat, document_format)
    )
    assert document.format.value in {"docx", "pptx", "pages", "keynote", "rtf"}


def test_styles_map_can_hold_semantic_heading_styles(office_modules) -> None:
    style = office_modules.models.DocumentStyle(font_size=18.0, bold=True)
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.DOCX,
        styles={"Heading1": style},
    )
    assert document.styles["Heading1"].font_size == 18.0


def test_table_cell_shading_and_borders_can_support_visual_contrast(office_modules) -> None:
    cell = office_modules.models.TableCell(
        shading_color="#000000",
        borders={"bottom": {"color": "#FFFFFF", "width": 1.0}},
    )
    assert cell.shading_color == "#000000"
    assert cell.borders["bottom"]["color"] == "#FFFFFF"
