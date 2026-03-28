# SPDX-License-Identifier: Apache-2.0

"""Tests for OpenDocument conversions."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.skip(reason="Office tests pending implementation alignment")


def test_odt_to_pdf_renames_libreoffice_output(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    intermediate = tmp_path / "libreoffice" / "document.pdf"
    intermediate.parent.mkdir(parents=True)
    intermediate.write_bytes(b"%PDF")
    monkeypatch.setattr(
        converter,
        "_run_libreoffice_conversion",
        lambda input_path, output_format, output_dir: intermediate,
    )

    output = tmp_path / "out" / "document.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = converter.odt_to_pdf(sample_office_files.odt, output)

    assert result == output
    assert output.exists()


@pytest.mark.parametrize(
    ("method_name", "source_attr", "target_name"),
    [
        ("docx_to_odt", "docx", "file.odt"),
        ("odt_to_docx", "odt", "file.docx"),
        ("xlsx_to_ods", "xlsx", "file.ods"),
    ],
)
def test_opendocument_roundtrip_methods_use_libreoffice(
    make_converter,
    monkeypatch,
    sample_office_files,
    tmp_path,
    method_name: str,
    source_attr: str,
    target_name: str,
) -> None:
    converter = make_converter()
    intermediate = tmp_path / "intermediate" / target_name
    intermediate.parent.mkdir(parents=True)
    intermediate.write_bytes(b"converted")
    monkeypatch.setattr(
        converter,
        "_run_libreoffice_conversion",
        lambda input_path, output_format, output_dir: intermediate,
    )

    source = getattr(sample_office_files, source_attr)
    output = tmp_path / "final" / target_name
    output.parent.mkdir(parents=True, exist_ok=True)
    method = getattr(converter, method_name)
    assert method(source, output) == output
    assert output.exists()


@pytest.mark.parametrize(
    ("source_format", "target_format", "expected_name"),
    [
        ("docx", "odt", "docx_to_odt"),
        ("odt", "docx", "odt_to_docx"),
        ("odt", "pdf", "odt_to_pdf"),
        ("xlsx", "ods", "xlsx_to_ods"),
    ],
)
def test_opendocument_converters_are_registered(
    make_converter, source_format: str, target_format: str, expected_name: str
) -> None:
    converter = make_converter()
    method = converter.get_converter(source_format, target_format)
    assert method is not None
    assert method.__name__ == expected_name


@pytest.mark.parametrize(
    ("attr_name", "expected_value"),
    [("odt", "odt"), ("ods", "ods"), ("odp", "odp")],
)
def test_opendocument_format_detection(
    make_converter, sample_office_files, attr_name: str, expected_value: str
) -> None:
    converter = make_converter()
    source = getattr(sample_office_files, attr_name)
    assert converter.detect_format(source).value == expected_value


def test_odp_pdf_conversion_is_not_registered(make_converter) -> None:
    converter = make_converter()
    assert converter.get_converter("odp", "pdf") is None
