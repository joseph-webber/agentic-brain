# SPDX-License-Identifier: Apache-2.0

"""Tests for RTF handling in office models and validation."""

from __future__ import annotations

import pytest


def test_model_office_format_includes_rtf(office_modules) -> None:
    assert office_modules.models.OfficeFormat.RTF.value == "rtf"


def test_document_content_can_represent_rtf_documents(
    office_modules, sample_paragraph
) -> None:
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.RTF,
        paragraphs=[sample_paragraph],
        document_properties={"generator": "TextEdit"},
    )
    assert document.format == office_modules.models.OfficeFormat.RTF
    assert document.paragraphs[0].runs[0].text == "Hello office"


def test_converter_does_not_detect_rtf_as_supported_conversion_format(
    make_converter, sample_office_files
) -> None:
    converter = make_converter()
    assert converter.detect_format(sample_office_files.rtf) is None


def test_converter_has_no_rtf_pdf_converter(make_converter) -> None:
    converter = make_converter()
    assert converter.get_converter("rtf", "pdf") is None
    assert converter.is_conversion_supported("rtf", "pdf") is False


@pytest.mark.parametrize("format_requested", ["rtf", "pages"])
def test_unsupported_office_format_error_stores_requested_value(
    office_modules, format_requested: str
) -> None:
    error = office_modules.exceptions.UnsupportedOfficeFormatError(format_requested)
    assert error.format_requested == format_requested
    assert str(error) == f"Unsupported office format: {format_requested}"


def test_invalid_document_structure_error_includes_element_id(office_modules) -> None:
    error = office_modules.exceptions.InvalidDocumentStructureError(
        "Malformed RTF table", element_id="tbl-9"
    )
    assert error.element_id == "tbl-9"
    assert "tbl-9" in str(error)


def test_document_validation_error_preserves_details(office_modules) -> None:
    error = office_modules.exceptions.DocumentValidationError(
        "RTF validation failed", details="unexpected control word"
    )
    assert error.details == "unexpected control word"
    assert str(error) == "RTF validation failed: unexpected control word"
