# SPDX-License-Identifier: Apache-2.0

"""Tests for RAG loaders used with office documents."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest


def test_docx_loader_basic_properties(rag_modules) -> None:
    loader = rag_modules.docx.DocxLoader()
    assert loader.source_name == "docx"
    assert loader.authenticate() is True
    assert loader.search("query") == []


def test_docx_loader_extract_text_returns_placeholder_when_dependency_missing(
    rag_modules, monkeypatch
) -> None:
    loader = rag_modules.docx.DocxLoader()
    monkeypatch.setattr(rag_modules.docx, "DOCX_AVAILABLE", False)
    assert loader._extract_text(b"docx") == "[DOCX content - install python-docx]"


def test_docx_loader_extract_text_reads_paragraphs_and_tables(
    rag_modules, monkeypatch
) -> None:
    loader = rag_modules.docx.DocxLoader()
    fake_doc = SimpleNamespace(
        paragraphs=[
            SimpleNamespace(text="Heading"),
            SimpleNamespace(text=""),
            SimpleNamespace(text="Body"),
        ],
        tables=[
            SimpleNamespace(
                rows=[
                    SimpleNamespace(
                        cells=[
                            SimpleNamespace(text="A1"),
                            SimpleNamespace(text="B1"),
                        ]
                    )
                ]
            )
        ],
    )
    monkeypatch.setattr(rag_modules.docx, "DOCX_AVAILABLE", True)
    monkeypatch.setattr(
        rag_modules.docx,
        "docx",
        SimpleNamespace(Document=lambda stream: fake_doc),
        raising=False,
    )
    assert loader._extract_text(b"docx-bytes") == "Heading\n\nBody\n\nA1 | B1"


def test_docx_loader_load_document_returns_none_for_missing_file(rag_modules, tmp_path) -> None:
    loader = rag_modules.docx.DocxLoader(base_path=str(tmp_path))
    assert loader.load_document("missing.docx") is None


def test_docx_loader_rejects_non_word_documents(rag_modules, tmp_path) -> None:
    other = tmp_path / "note.txt"
    other.write_text("hello", encoding="utf-8")
    loader = rag_modules.docx.DocxLoader(base_path=str(tmp_path))
    assert loader.load_document(str(other)) is None


def test_docx_loader_load_document_builds_loaded_document(
    rag_modules, monkeypatch, sample_office_files
) -> None:
    loader = rag_modules.docx.DocxLoader()
    monkeypatch.setattr(loader, "_extract_text", lambda data: "Extracted body")
    document = loader.load_document(str(sample_office_files.docx))
    assert document is not None
    assert document.content == "Extracted body"
    assert document.filename == "sample.docx"
    assert document.source == "docx"


def test_docx_loader_load_folder_recursive_includes_nested_docs(
    rag_modules, monkeypatch, sample_office_files
) -> None:
    loader = rag_modules.docx.DocxLoader(base_path=str(sample_office_files.root))
    monkeypatch.setattr(
        loader,
        "load_document",
        lambda doc_id: SimpleNamespace(filename=BytesIO(str(doc_id).encode()).getvalue().decode()),
    )
    docs = loader.load_folder(".", recursive=True)
    filenames = sorted(doc.filename for doc in docs)
    assert "office-files/sample.docx" not in filenames
    assert any(name.endswith("inside.docx") for name in filenames)


def test_docx_loader_load_folder_nonrecursive_excludes_nested_docs(
    rag_modules, monkeypatch, sample_office_files
) -> None:
    loader = rag_modules.docx.DocxLoader(base_path=str(sample_office_files.root))
    monkeypatch.setattr(
        loader,
        "load_document",
        lambda doc_id: SimpleNamespace(filename=str(doc_id)),
    )
    docs = loader.load_folder(".", recursive=False)
    filenames = [doc.filename for doc in docs]
    assert all("nested" not in name for name in filenames)


def test_word_loader_alias_points_to_docx_loader(rag_modules) -> None:
    assert rag_modules.docx.WordLoader is rag_modules.docx.DocxLoader


def test_excel_loader_basic_properties(rag_modules) -> None:
    loader = rag_modules.csv_loader.ExcelLoader()
    assert loader.source_name == "excel"
    assert loader.authenticate() is True
    assert loader.search("query") == []


def test_excel_loader_uses_pandas_when_available(rag_modules, monkeypatch) -> None:
    loader = rag_modules.csv_loader.ExcelLoader(sheet_names=["Summary"], max_rows=5)
    fake_df = SimpleNamespace(to_string=lambda index=False: "Revenue 42")
    fake_pd = SimpleNamespace(
        ExcelFile=lambda file_obj: SimpleNamespace(sheet_names=["Summary", "Other"]),
        read_excel=lambda xls, sheet_name, nrows: fake_df,
    )
    monkeypatch.setattr(rag_modules.csv_loader, "PANDAS_AVAILABLE", True)
    monkeypatch.setattr(rag_modules.csv_loader, "pd", fake_pd, raising=False)
    text = loader._excel_to_text(b"excel")
    assert "## Sheet: Summary" in text
    assert "Revenue 42" in text


def test_excel_loader_falls_back_to_openpyxl(rag_modules, monkeypatch) -> None:
    loader = rag_modules.csv_loader.ExcelLoader(sheet_names=["Summary"], max_rows=5)

    class FakeSheet:
        def iter_rows(self, values_only=True):
            return iter([("Name", "Value"), ("Revenue", 42)])

    class FakeWorkbook:
        sheetnames = ["Summary"]

        def __getitem__(self, item):
            return FakeSheet()

    monkeypatch.setattr(rag_modules.csv_loader, "PANDAS_AVAILABLE", False)
    monkeypatch.setattr(rag_modules.csv_loader, "OPENPYXL_AVAILABLE", True)
    monkeypatch.setattr(
        rag_modules.csv_loader,
        "openpyxl",
        SimpleNamespace(load_workbook=lambda file_obj, read_only=True: FakeWorkbook()),
        raising=False,
    )
    text = loader._excel_to_text(b"excel")
    assert "## Sheet: Summary" in text
    assert "Revenue | 42" in text


def test_excel_loader_returns_placeholder_when_no_parser_available(
    rag_modules, monkeypatch
) -> None:
    loader = rag_modules.csv_loader.ExcelLoader()
    monkeypatch.setattr(rag_modules.csv_loader, "PANDAS_AVAILABLE", False)
    monkeypatch.setattr(rag_modules.csv_loader, "OPENPYXL_AVAILABLE", False)
    assert loader._excel_to_text(b"excel") == "[Excel content - install pandas or openpyxl]"


def test_excel_loader_rejects_non_excel_files(rag_modules, tmp_path) -> None:
    other = tmp_path / "note.txt"
    other.write_text("hello", encoding="utf-8")
    loader = rag_modules.csv_loader.ExcelLoader(base_path=str(tmp_path))
    assert loader.load_document(str(other)) is None


def test_excel_loader_load_document_builds_loaded_document(
    rag_modules, monkeypatch, sample_office_files
) -> None:
    loader = rag_modules.csv_loader.ExcelLoader()
    monkeypatch.setattr(loader, "_excel_to_text", lambda data: "Sheet data")
    document = loader.load_document(str(sample_office_files.xlsx))
    assert document is not None
    assert document.content == "Sheet data"
    assert document.filename == "sheet.xlsx"
    assert document.source == "excel"


@pytest.mark.parametrize("recursive", [False, True])
def test_excel_loader_load_folder_discovers_excel_files(
    rag_modules, monkeypatch, sample_office_files, recursive: bool
) -> None:
    loader = rag_modules.csv_loader.ExcelLoader(base_path=str(sample_office_files.root))
    monkeypatch.setattr(
        loader,
        "load_document",
        lambda doc_id: SimpleNamespace(filename=str(doc_id)),
    )
    docs = loader.load_folder(".", recursive=recursive)
    filenames = [doc.filename for doc in docs]
    if recursive:
        assert any("nested/inside.xlsx" in name for name in filenames)
    else:
        assert all("nested/inside.xlsx" not in name for name in filenames)
