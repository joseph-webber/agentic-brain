"""Tests for Apple Pages conversions."""

from __future__ import annotations

import pytest


def test_pages_to_pdf_delegates_to_macos_automation(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter(platform_name="Darwin")
    calls: list[tuple[str, str, str]] = []

    def fake_run(app_name, input_path, output_path):
        calls.append((app_name, str(input_path), str(output_path)))
        output_path.write_bytes(b"%PDF")
        return output_path

    monkeypatch.setattr(converter, "_run_macos_automation", fake_run)
    output = tmp_path / "pages.pdf"
    result = converter.pages_to_pdf(sample_office_files.pages, output)

    assert result == output
    assert calls == [("Pages", str(sample_office_files.pages), str(output))]


def test_pages_converter_registration(make_converter) -> None:
    converter = make_converter()
    method = converter.get_converter("pages", "pdf")
    assert method is not None
    assert method.__name__ == "pages_to_pdf"


def test_pages_to_pdf_surfaces_conversion_error(
    make_converter, monkeypatch, office_modules, sample_office_files, tmp_path
) -> None:
    converter = make_converter(platform_name="Darwin")
    monkeypatch.setattr(
        converter,
        "_run_macos_automation",
        lambda app_name, input_path, output_path: (_ for _ in ()).throw(
            office_modules.converter.ConversionError("automation failed")
        ),
    )
    with pytest.raises(office_modules.converter.ConversionError, match="automation"):
        converter.pages_to_pdf(sample_office_files.pages, tmp_path / "out.pdf")


def test_pages_format_detection(make_converter, sample_office_files) -> None:
    converter = make_converter()
    assert converter.detect_format(sample_office_files.pages).value == "pages"
