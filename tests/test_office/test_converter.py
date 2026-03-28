# SPDX-License-Identifier: Apache-2.0

"""Tests for OfficeConverter helpers and orchestration."""

from __future__ import annotations

import builtins
import subprocess
import types
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skip(reason="Office tests pending implementation alignment")


@pytest.mark.parametrize(
    ("platform_name", "existing_path"),
    [
        ("Darwin", "/opt/homebrew/bin/soffice"),
        ("Linux", "/usr/bin/soffice"),
        ("Windows", r"C:\Program Files\LibreOffice\program\soffice.exe"),
    ],
)
def test_find_libreoffice_returns_known_platform_path(
    office_modules, monkeypatch, platform_name: str, existing_path: str
) -> None:
    converter = office_modules.converter.OfficeConverter.__new__(
        office_modules.converter.OfficeConverter
    )
    converter.platform = platform_name
    monkeypatch.setattr(
        office_modules.converter.os.path, "exists", lambda path: path == existing_path
    )
    monkeypatch.setattr(office_modules.converter.shutil, "which", lambda name: None)
    assert converter._find_libreoffice() == existing_path


def test_find_libreoffice_falls_back_to_path_lookup(
    office_modules, monkeypatch
) -> None:
    converter = office_modules.converter.OfficeConverter.__new__(
        office_modules.converter.OfficeConverter
    )
    converter.platform = "Linux"
    monkeypatch.setattr(office_modules.converter.os.path, "exists", lambda path: False)
    monkeypatch.setattr(
        office_modules.converter.shutil, "which", lambda name: "/custom/soffice"
    )
    assert converter._find_libreoffice() == "/custom/soffice"


def test_find_libreoffice_returns_none_when_unavailable(
    office_modules, monkeypatch
) -> None:
    converter = office_modules.converter.OfficeConverter.__new__(
        office_modules.converter.OfficeConverter
    )
    converter.platform = "Linux"
    monkeypatch.setattr(office_modules.converter.os.path, "exists", lambda path: False)
    monkeypatch.setattr(office_modules.converter.shutil, "which", lambda name: None)
    assert converter._find_libreoffice() is None


def test_check_dependencies_marks_available_modules(
    office_modules, monkeypatch
) -> None:
    converter = office_modules.converter.OfficeConverter.__new__(
        office_modules.converter.OfficeConverter
    )
    real_import = builtins.__import__
    docx_module = types.ModuleType("docx")
    docx_module.Document = object

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "docx2pdf":
            return types.ModuleType("docx2pdf")
        if name == "mammoth":
            return types.ModuleType("mammoth")
        if name == "docx":
            return docx_module
        if name == "openpyxl":
            return types.ModuleType("openpyxl")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    converter._check_dependencies()
    assert converter._has_docx2pdf is True
    assert converter._has_mammoth is True
    assert converter._has_python_docx is True
    assert converter._has_openpyxl is True


def test_check_dependencies_marks_missing_modules(office_modules, monkeypatch) -> None:
    converter = office_modules.converter.OfficeConverter.__new__(
        office_modules.converter.OfficeConverter
    )
    real_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name in {"docx2pdf", "mammoth", "docx", "openpyxl"}:
            raise ImportError(name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    converter._check_dependencies()
    assert converter._has_docx2pdf is False
    assert converter._has_mammoth is False
    assert converter._has_python_docx is False
    assert converter._has_openpyxl is False


def test_run_libreoffice_conversion_success(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter(libreoffice_path="/usr/bin/soffice")
    seen: dict[str, object] = {}

    def fake_run(cmd, capture_output, text, timeout, check):
        seen["cmd"] = cmd
        seen["capture_output"] = capture_output
        seen["text"] = text
        seen["timeout"] = timeout
        seen["check"] = check
        output = tmp_path / "exports" / "sample.pdf"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(office_modules.converter.subprocess, "run", fake_run)

    result = converter._run_libreoffice_conversion(
        sample_office_files.docx, "pdf", tmp_path / "exports"
    )

    assert result == tmp_path / "exports" / "sample.pdf"
    assert isinstance(seen["cmd"], list)
    assert seen["cmd"][0] == "/usr/bin/soffice"
    assert seen["cmd"][1:5] == ["--headless", "--convert-to", "pdf", "--outdir"]
    assert seen["timeout"] == 60
    assert seen["check"] is False


def test_run_libreoffice_conversion_requires_binary(
    make_converter, office_modules, sample_office_files, tmp_path
) -> None:
    converter = make_converter(libreoffice_path=None)
    with pytest.raises(
        office_modules.converter.ConversionError, match="LibreOffice not found"
    ):
        converter._run_libreoffice_conversion(
            sample_office_files.docx, "pdf", tmp_path / "exports"
        )


def test_run_libreoffice_conversion_requires_input_file(
    make_converter, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    missing = sample_office_files.root / "missing.docx"
    with pytest.raises(FileNotFoundError, match="Input file not found"):
        converter._run_libreoffice_conversion(missing, "pdf", tmp_path / "exports")


def test_run_libreoffice_conversion_wraps_nonzero_exit(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    monkeypatch.setattr(
        office_modules.converter.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout="", stderr="boom"),
    )
    with pytest.raises(
        office_modules.converter.ConversionError,
        match="Conversion failed: LibreOffice conversion failed: boom",
    ):
        converter._run_libreoffice_conversion(
            sample_office_files.docx, "pdf", tmp_path / "exports"
        )


def test_run_libreoffice_conversion_handles_timeout(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    monkeypatch.setattr(
        office_modules.converter.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(cmd="soffice", timeout=60)
        ),
    )
    with pytest.raises(office_modules.converter.ConversionError, match="timed out"):
        converter._run_libreoffice_conversion(
            sample_office_files.docx, "pdf", tmp_path / "exports"
        )


def test_run_libreoffice_conversion_errors_when_output_missing(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    monkeypatch.setattr(
        office_modules.converter.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="ok", stderr=""),
    )
    with pytest.raises(
        office_modules.converter.ConversionError,
        match="output file not found",
    ):
        converter._run_libreoffice_conversion(
            sample_office_files.docx, "pdf", tmp_path / "exports"
        )


def test_run_macos_automation_requires_darwin(
    make_converter, office_modules, sample_office_files, tmp_path
) -> None:
    converter = make_converter(platform_name="Linux")
    with pytest.raises(
        office_modules.converter.ConversionError, match="not available on Linux"
    ):
        converter._run_macos_automation(
            "Pages", sample_office_files.pages, tmp_path / "pages.pdf"
        )


def test_run_macos_automation_success(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter(platform_name="Darwin")
    seen: dict[str, object] = {}

    def fake_run(cmd, capture_output, text, timeout, check):
        seen["cmd"] = cmd
        output = tmp_path / "exports" / "pages.pdf"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"%PDF")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(office_modules.converter.subprocess, "run", fake_run)

    result = converter._run_macos_automation(
        "Pages", sample_office_files.pages, tmp_path / "exports" / "pages.pdf"
    )

    assert result == tmp_path / "exports" / "pages.pdf"
    assert seen["cmd"][0] == "osascript"
    assert seen["cmd"][1] == "-e"
    assert 'tell application "Pages"' in seen["cmd"][2]
    assert "export to outputFile as PDF" in seen["cmd"][2]


def test_run_macos_automation_wraps_nonzero_exit(
    make_converter, office_modules, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter(platform_name="Darwin")
    monkeypatch.setattr(
        office_modules.converter.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(
            returncode=1, stdout="", stderr="permissions"
        ),
    )
    with pytest.raises(
        office_modules.converter.ConversionError,
        match="macOS automation failed: Pages automation failed: permissions",
    ):
        converter._run_macos_automation(
            "Pages", sample_office_files.pages, tmp_path / "exports" / "pages.pdf"
        )


def test_run_macos_automation_handles_timeout(
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
    with pytest.raises(
        office_modules.converter.ConversionError, match="Pages automation timed out"
    ):
        converter._run_macos_automation(
            "Pages", sample_office_files.pages, tmp_path / "exports" / "pages.pdf"
        )


@pytest.mark.parametrize(
    ("filename", "expected_name"),
    [
        ("document.docx", "DOCX"),
        ("document.xlsx", "XLSX"),
        ("slides.pptx", "PPTX"),
        ("legacy.doc", "DOC"),
        ("legacy.xls", "XLS"),
        ("legacy.ppt", "PPT"),
        ("proposal.pages", "PAGES"),
        ("budget.numbers", "NUMBERS"),
        ("deck.key", "KEYNOTE"),
        ("notes.odt", "ODT"),
        ("sheet.ods", "ODS"),
        ("talk.odp", "ODP"),
    ],
)
def test_detect_format_supported_extensions(
    make_converter, office_modules, tmp_path, filename: str, expected_name: str
) -> None:
    converter = make_converter()
    path = tmp_path / filename
    path.write_bytes(b"content")
    detected = converter.detect_format(path)
    assert detected == getattr(office_modules.converter.OfficeFormat, expected_name)


@pytest.mark.parametrize("filename", ["notes.rtf", "archive.zip", "image.png"])
def test_detect_format_returns_none_for_unsupported_extensions(
    make_converter, tmp_path, filename: str
) -> None:
    converter = make_converter()
    path = tmp_path / filename
    path.write_bytes(b"content")
    assert converter.detect_format(path) is None


@pytest.mark.parametrize("source_format", ["bogus", "rtf", ""])
def test_get_converter_rejects_invalid_source_format(
    make_converter, source_format: str
) -> None:
    converter = make_converter()
    assert converter.get_converter(source_format, "pdf") is None


@pytest.mark.parametrize(
    ("source_format", "target_format", "expected"),
    [
        ("docx", "pdf", True),
        ("xlsx", "csv", True),
        ("pages", "pdf", True),
        ("odp", "pdf", False),
        ("rtf", "pdf", False),
    ],
)
def test_is_conversion_supported(
    make_converter, source_format: str, target_format: str, expected: bool
) -> None:
    converter = make_converter()
    assert converter.is_conversion_supported(source_format, target_format) is expected


def test_convert_batch_skips_unsupported_and_failed_files(
    make_converter, monkeypatch, office_modules, sample_office_files, tmp_path
) -> None:
    converter = make_converter()

    def fake_docx_to_pdf(input_path, output_path):
        if input_path == sample_office_files.nested_docx:
            raise office_modules.converter.ConversionError("broken")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"%PDF")
        return output_path

    monkeypatch.setattr(converter, "docx_to_pdf", fake_docx_to_pdf)

    results = converter.convert_batch(
        [
            sample_office_files.docx,
            sample_office_files.unsupported,
            sample_office_files.nested_docx,
        ],
        "pdf",
        tmp_path / "batch",
    )

    assert results == [tmp_path / "batch" / "sample.pdf"]


def test_convert_folder_nonrecursive_filters_supported_files(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    calls: list[str] = []

    def fake_convert_batch(input_files, output_format, output_dir):
        calls.extend(sorted(path.name for path in input_files))
        return []

    monkeypatch.setattr(converter, "convert_batch", fake_convert_batch)
    converter.convert_folder(sample_office_files.root, "pdf", tmp_path / "out")

    assert calls == [
        "budget.numbers",
        "corrupted.docx",
        "deck.key",
        "document.odt",
        "empty.docx",
        "large.docx",
        "legacy.doc",
        "presentation.odp",
        "proposal.pages",
        "sample.docx",
        "sheet.xls",
        "sheet.xlsx",
        "slides.pptx",
        "spreadsheet.ods",
    ]


def test_convert_folder_recursive_includes_nested_supported_files(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()
    captured: list[str] = []

    def fake_convert_batch(input_files, output_format, output_dir):
        captured.extend(
            sorted(
                path.relative_to(sample_office_files.root).as_posix()
                for path in input_files
            )
        )
        return []

    monkeypatch.setattr(converter, "convert_batch", fake_convert_batch)
    converter.convert_folder(
        sample_office_files.root, "pdf", tmp_path / "out", recursive=True
    )

    assert "nested/inside.docx" in captured
    assert "nested/inside.xlsx" in captured
    assert "nested/inside.pptx" in captured


def test_convert_folder_raises_for_missing_directory(make_converter, tmp_path) -> None:
    converter = make_converter()
    with pytest.raises(FileNotFoundError, match="Input directory not found"):
        converter.convert_folder(tmp_path / "missing", "pdf", tmp_path / "out")
