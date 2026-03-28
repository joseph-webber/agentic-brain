# SPDX-License-Identifier: Apache-2.0

"""Tests for PowerPoint-focused conversion behavior."""

from __future__ import annotations

import pytest


def test_pptx_to_pdf_renames_libreoffice_output(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    intermediate = tmp_path / "libreoffice" / "slides.pdf"
    intermediate.parent.mkdir(parents=True)
    intermediate.write_bytes(b"%PDF")
    monkeypatch.setattr(
        converter,
        "_run_libreoffice_conversion",
        lambda input_path, output_format, output_dir: intermediate,
    )

    output = tmp_path / "final" / "deck.pdf"
    output.parent.mkdir(parents=True, exist_ok=True)
    assert converter.pptx_to_pdf(sample_office_files.pptx, output) == output
    assert output.exists()


def test_pptx_to_pdf_keeps_existing_target_name(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    output = tmp_path / "slides.pdf"
    output.write_bytes(b"%PDF")
    monkeypatch.setattr(
        converter,
        "_run_libreoffice_conversion",
        lambda input_path, output_format, output_dir: output,
    )
    assert converter.pptx_to_pdf(sample_office_files.pptx, output) == output


def test_pptx_converter_registration(make_converter) -> None:
    converter = make_converter()
    method = converter.get_converter("pptx", "pdf")
    assert method is not None
    assert method.__name__ == "pptx_to_pdf"


@pytest.mark.parametrize("extension", [".pptx", ".ppt"])
def test_presentation_format_detection(
    make_converter, tmp_path, extension: str
) -> None:
    converter = make_converter()
    path = tmp_path / f"slides{extension}"
    path.write_bytes(b"presentation")
    detected = converter.detect_format(path)
    assert detected.value == extension.lstrip(".")


def test_legacy_ppt_to_pdf_not_registered(make_converter) -> None:
    converter = make_converter()
    assert converter.get_converter("ppt", "pdf") is None
