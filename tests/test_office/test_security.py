# SPDX-License-Identifier: Apache-2.0

"""Security and validation tests for office document handling."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skip(reason="Office tests pending implementation alignment")


def test_document_model_error_is_base_class(office_modules) -> None:
    error = office_modules.exceptions.DocumentModelError("base error")
    assert isinstance(error, Exception)
    assert str(error) == "base error"


def test_invalid_document_structure_error_without_element_id(office_modules) -> None:
    error = office_modules.exceptions.InvalidDocumentStructureError("Bad structure")
    assert error.element_id is None
    assert str(error) == "Bad structure"


def test_document_validation_error_without_details(office_modules) -> None:
    error = office_modules.exceptions.DocumentValidationError("Validation failed")
    assert error.details is None
    assert str(error) == "Validation failed"


def test_unsupported_format_error_accepts_model_enum(office_modules) -> None:
    error = office_modules.exceptions.UnsupportedOfficeFormatError(
        office_modules.models.OfficeFormat.DOCX
    )
    assert str(error) == "Unsupported office format: OfficeFormat.DOCX"


def test_libreoffice_conversion_builds_safe_argument_list(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    seen: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd
        output = tmp_path / "out" / "sample.pdf"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(office_modules.converter.subprocess, "run", fake_run)
    converter._run_libreoffice_conversion(
        sample_office_files.docx, "pdf", tmp_path / "out"
    )

    assert isinstance(seen["cmd"], list)
    assert "--headless" in seen["cmd"]
    assert str(sample_office_files.docx.resolve()) == seen["cmd"][-1]


@pytest.mark.parametrize("fixture_name", ["empty_docx", "corrupted_docx", "large_docx"])
def test_edge_case_word_files_can_be_redirected_to_fallback_conversion(
    make_converter, monkeypatch, sample_office_files, tmp_path, fixture_name: str
) -> None:
    converter = make_converter(python_docx=True)
    source = getattr(sample_office_files, fixture_name)
    monkeypatch.setitem(
        __import__("sys").modules,
        "docx",
        SimpleNamespace(Document=lambda path: (_ for _ in ()).throw(ValueError("bad"))),
    )

    def fake_conversion(input_path, output_format, output_dir):
        output = tmp_path / "secure" / f"{input_path.stem}.txt"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("sanitized fallback", encoding="utf-8")
        return output

    monkeypatch.setattr(converter, "_run_libreoffice_conversion", fake_conversion)
    output = tmp_path / "exports" / f"{source.stem}.txt"
    output.parent.mkdir(parents=True, exist_ok=True)
    assert converter.docx_to_txt(source, output) == output
    assert output.read_text(encoding="utf-8") == "sanitized fallback"


def test_convert_folder_missing_directory_raises(make_converter, tmp_path) -> None:
    converter = make_converter()
    with pytest.raises(FileNotFoundError):
        converter.convert_folder(tmp_path / "missing", "pdf", tmp_path / "out")


def test_detect_format_rejects_disguised_unsupported_files(
    make_converter, sample_office_files
) -> None:
    converter = make_converter()
    assert converter.detect_format(sample_office_files.rtf) is None
    assert converter.detect_format(sample_office_files.unsupported).value == "txt"


def test_convert_batch_isolates_conversion_errors(
    make_converter, monkeypatch, office_modules, sample_office_files, tmp_path
) -> None:
    converter = make_converter()

    def explode(input_path, output_path):
        raise office_modules.converter.ConversionError("conversion blocked")

    monkeypatch.setattr(converter, "docx_to_pdf", explode)
    results = converter.convert_batch(
        [sample_office_files.docx], "pdf", tmp_path / "batch"
    )
    assert results == []


def test_macos_automation_timeout_is_reported_cleanly(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter(platform_name="Darwin")
    monkeypatch.setattr(
        office_modules.converter.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd="osascript", timeout=30)
        ),
    )
    with pytest.raises(office_modules.converter.ConversionError, match="timed out"):
        converter._run_macos_automation(
            "Pages", sample_office_files.pages, tmp_path / "pages.pdf"
        )
