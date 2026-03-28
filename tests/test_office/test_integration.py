"""End-to-end office module integration tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


@pytest.mark.parametrize(
    ("fixture_name", "method_name", "target_name"),
    [
        ("docx", "docx_to_pdf", "sample.pdf"),
        ("xlsx", "xlsx_to_pdf", "sheet.pdf"),
        ("pptx", "pptx_to_pdf", "slides.pdf"),
        ("pages", "pages_to_pdf", "proposal.pdf"),
        ("numbers", "numbers_to_pdf", "budget.pdf"),
        ("key", "keynote_to_pdf", "deck.pdf"),
        ("odt", "odt_to_pdf", "document.pdf"),
    ],
)
def test_individual_converters_can_be_exercised_end_to_end(
    make_converter,
    monkeypatch,
    sample_office_files,
    tmp_path,
    fixture_name: str,
    method_name: str,
    target_name: str,
) -> None:
    converter = make_converter(platform_name="Darwin")

    def fake_libreoffice(input_path, output_format, output_dir):
        output = output_dir / f"{input_path.stem}.{output_format}"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"converted")
        return output

    def fake_macos(app_name, input_path, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"converted")
        return output_path

    monkeypatch.setattr(converter, "_run_libreoffice_conversion", fake_libreoffice)
    monkeypatch.setattr(converter, "_run_macos_automation", fake_macos)

    source = getattr(sample_office_files, fixture_name)
    output = tmp_path / "out" / target_name
    method = getattr(converter, method_name)
    result = method(source, output)

    assert result == output
    assert output.exists()


def test_convert_batch_mixed_formats_to_pdf(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter(platform_name="Darwin")

    def write_output(input_path, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(input_path.suffix.encode())
        return output_path

    monkeypatch.setattr(converter, "docx_to_pdf", write_output)
    monkeypatch.setattr(converter, "xlsx_to_pdf", write_output)
    monkeypatch.setattr(converter, "pptx_to_pdf", write_output)
    monkeypatch.setattr(converter, "pages_to_pdf", write_output)

    results = converter.convert_batch(
        [
            sample_office_files.docx,
            sample_office_files.xlsx,
            sample_office_files.pptx,
            sample_office_files.pages,
            sample_office_files.unsupported,
        ],
        "pdf",
        tmp_path / "batch",
    )

    assert sorted(path.name for path in results) == [
        "proposal.pdf",
        "sample.pdf",
        "sheet.pdf",
        "slides.pdf",
    ]


def test_convert_folder_recursive_preserves_nested_supported_files(
    make_converter, monkeypatch, sample_office_files, tmp_path
) -> None:
    converter = make_converter()

    def fake_convert_batch(input_files, output_format, output_dir):
        results = []
        for input_file in input_files:
            output = output_dir / f"{input_file.stem}.{output_format}"
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(b"%PDF")
            results.append(output)
        return results

    monkeypatch.setattr(converter, "convert_batch", fake_convert_batch)
    results = converter.convert_folder(
        sample_office_files.root, "pdf", tmp_path / "pdfs", recursive=True
    )

    names = {path.name for path in results}
    assert "inside.pdf" in names
    assert "sample.pdf" in names


def test_document_content_can_represent_word_table_and_image_workflow(
    office_modules, sample_image, sample_paragraph, sample_table
) -> None:
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.DOCX,
        paragraphs=[sample_paragraph],
        tables=[sample_table],
        images=[sample_image],
        metadata=office_modules.models.Metadata(title="Quarterly report"),
    )
    assert document.metadata.title == "Quarterly report"
    assert document.tables[0].cell_grid["A1"].paragraphs[0].runs[0].text == "Hello office"
    assert document.images[0].alternate_text == "Quarterly revenue chart"


def test_document_content_can_represent_spreadsheet_workflow(office_modules) -> None:
    cell = office_modules.models.Cell(reference="A1", value=42)
    worksheet = office_modules.models.Worksheet(name="Summary", cells={"A1": cell})
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.XLSX,
        worksheets=[worksheet],
    )
    assert document.worksheets[0].cells["A1"].value == 42


def test_document_content_can_represent_presentation_workflow(
    office_modules, sample_paragraph, sample_image
) -> None:
    slide = office_modules.models.Slide(
        title=sample_paragraph,
        body=[sample_paragraph],
        images=[sample_image],
        background="#000000",
    )
    document = office_modules.models.DocumentContent(
        format=office_modules.models.OfficeFormat.PPTX,
        slides=[slide],
    )
    assert document.slides[0].background == "#000000"
    assert document.slides[0].images[0].title == "Chart"


def test_rag_docx_loader_can_process_office_fixture(
    rag_modules, monkeypatch, sample_office_files
) -> None:
    loader = rag_modules.docx.DocxLoader()
    monkeypatch.setattr(loader, "_extract_text", lambda data: "Loaded from fixture")
    document = loader.load_document(str(sample_office_files.docx))
    assert document is not None
    assert document.content == "Loaded from fixture"


def test_rag_excel_loader_can_process_office_fixture(
    rag_modules, monkeypatch, sample_office_files
) -> None:
    loader = rag_modules.csv_loader.ExcelLoader()
    monkeypatch.setattr(loader, "_excel_to_text", lambda data: "Excel fixture")
    document = loader.load_document(str(sample_office_files.xlsx))
    assert document is not None
    assert document.content == "Excel fixture"


@pytest.mark.parametrize(
    "fixture_name",
    ["empty_docx", "corrupted_docx", "large_docx"],
)
def test_edge_case_fixtures_exist_for_integration(sample_office_files, fixture_name: str) -> None:
    path = getattr(sample_office_files, fixture_name)
    assert path.exists()
    if fixture_name == "large_docx":
        assert path.stat().st_size >= 1024 * 1024


@pytest.mark.parametrize(
    ("source_format", "target_format"),
    [
        ("docx", "pdf"),
        ("docx", "txt"),
        ("docx", "html"),
        ("xlsx", "csv"),
        ("xlsx", "ods"),
        ("pages", "pdf"),
        ("numbers", "pdf"),
        ("key", "pdf"),
        ("odt", "docx"),
    ],
)
def test_supported_conversion_matrix(make_converter, source_format: str, target_format: str) -> None:
    converter = make_converter()
    assert converter.is_conversion_supported(source_format, target_format) is True
