# SPDX-License-Identifier: Apache-2.0

"""Shared fixtures for office document service tests."""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# Optional dependency availability flags
# Tests that require specific packages use these to skip gracefully.
# ---------------------------------------------------------------------------
_OPTIONAL_SPECS = {
    "docx": "python-docx",
    "openpyxl": "openpyxl",
    "pptx": "python-pptx",
    "mammoth": "mammoth",
    "odf": "odfpy",
    "striprtf": "striprtf",
    "PIL": "Pillow",
    "snappy": "python-snappy",
    "pandas": "pandas",
    "html2text": "html2text",
    "docx2pdf": "docx2pdf",
}


def _check_available(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


DOCX_AVAILABLE = _check_available("docx")
OPENPYXL_AVAILABLE = _check_available("openpyxl")
PPTX_AVAILABLE = _check_available("pptx")
MAMMOTH_AVAILABLE = _check_available("mammoth")
ODF_AVAILABLE = _check_available("odf")
STRIPRTF_AVAILABLE = _check_available("striprtf")
PIL_AVAILABLE = _check_available("PIL")
SNAPPY_AVAILABLE = _check_available("snappy")
PANDAS_AVAILABLE = _check_available("pandas")
HTML2TEXT_AVAILABLE = _check_available("html2text")
DOCX2PDF_AVAILABLE = _check_available("docx2pdf")

# Convenience skip markers for use in test files
requires_docx = pytest.mark.skipif(
    not DOCX_AVAILABLE, reason="python-docx not installed"
)
requires_openpyxl = pytest.mark.skipif(
    not OPENPYXL_AVAILABLE, reason="openpyxl not installed"
)
requires_pptx = pytest.mark.skipif(
    not PPTX_AVAILABLE, reason="python-pptx not installed"
)
requires_mammoth = pytest.mark.skipif(
    not MAMMOTH_AVAILABLE, reason="mammoth not installed"
)
requires_odf = pytest.mark.skipif(not ODF_AVAILABLE, reason="odfpy not installed")
requires_striprtf = pytest.mark.skipif(
    not STRIPRTF_AVAILABLE, reason="striprtf not installed"
)
requires_pil = pytest.mark.skipif(not PIL_AVAILABLE, reason="Pillow not installed")
requires_snappy = pytest.mark.skipif(
    not SNAPPY_AVAILABLE, reason="python-snappy not installed"
)
requires_pandas = pytest.mark.skipif(
    not PANDAS_AVAILABLE, reason="pandas not installed"
)

REPO_ROOT = Path(__file__).resolve().parents[2]
OFFICE_ROOT = REPO_ROOT / "src" / "agentic_brain" / "documents" / "services" / "office"
FIXTURES_ROOT = Path(__file__).resolve().parent / "fixtures"
_TEST_PACKAGE = "_office_testpkg"


def _ensure_package(name: str, path: Path) -> None:
    if name in sys.modules:
        return
    module = types.ModuleType(name)
    module.__path__ = [str(path)]  # type: ignore[attr-defined]
    sys.modules[name] = module


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_ensure_package(_TEST_PACKAGE, OFFICE_ROOT)
OFFICE_MODELS = _load_module(f"{_TEST_PACKAGE}.models", OFFICE_ROOT / "models.py")
OFFICE_EXCEPTIONS = _load_module(
    f"{_TEST_PACKAGE}.exceptions", OFFICE_ROOT / "exceptions.py"
)
OFFICE_CONVERTER = _load_module(
    f"{_TEST_PACKAGE}.converter", OFFICE_ROOT / "converter.py"
)
OFFICE_EXCEL = _load_module(f"{_TEST_PACKAGE}.excel", OFFICE_ROOT / "excel.py")
OFFICE_PAGES = _load_module(
    f"{_TEST_PACKAGE}.apple_pages", OFFICE_ROOT / "apple_pages.py"
)


@pytest.fixture(scope="session")
def office_modules() -> SimpleNamespace:
    """Provide path-loaded office modules without importing documents package."""
    return SimpleNamespace(
        models=OFFICE_MODELS,
        exceptions=OFFICE_EXCEPTIONS,
        converter=OFFICE_CONVERTER,
        excel=OFFICE_EXCEL,
        apple_pages=OFFICE_PAGES,
    )


@pytest.fixture(scope="session")
def rag_modules() -> SimpleNamespace:
    """Provide RAG loader modules used by office integration tests."""
    try:
        return SimpleNamespace(
            base=importlib.import_module("agentic_brain.rag.loaders.base"),
            docx=importlib.import_module("agentic_brain.rag.loaders.docx"),
            csv_loader=importlib.import_module("agentic_brain.rag.loaders.csv_loader"),
        )
    except (ImportError, ModuleNotFoundError) as exc:
        pytest.skip(f"RAG loader modules not available: {exc}")


@pytest.fixture
def make_converter(office_modules, monkeypatch):
    """Create an OfficeConverter with fully controlled dependency flags."""

    def _make(
        *,
        platform_name: str = "Linux",
        libreoffice_path: str | None = "/usr/bin/soffice",
        docx2pdf: bool = False,
        mammoth: bool = False,
        python_docx: bool = False,
        openpyxl: bool = False,
    ):
        monkeypatch.setattr(
            office_modules.converter.platform, "system", lambda: platform_name
        )

        def fake_check(self) -> None:
            self._has_docx2pdf = docx2pdf
            self._has_mammoth = mammoth
            self._has_python_docx = python_docx
            self._has_openpyxl = openpyxl

        monkeypatch.setattr(
            office_modules.converter.OfficeConverter,
            "_check_dependencies",
            fake_check,
        )
        return office_modules.converter.OfficeConverter(
            libreoffice_path=libreoffice_path
        )

    return _make


@pytest.fixture
def sample_office_files(tmp_path) -> SimpleNamespace:
    """Create representative office files used across tests."""
    root = tmp_path / "office-files"
    root.mkdir()

    def write_bytes(name: str, data: bytes) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def write_text(name: str, data: str) -> Path:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data, encoding="utf-8")
        return path

    return SimpleNamespace(
        root=root,
        docx=write_bytes("sample.docx", b"PK\x03\x04fake-docx"),
        doc=write_bytes("legacy.doc", b"legacy-word"),
        xlsx=write_bytes("sheet.xlsx", b"PK\x03\x04fake-xlsx"),
        xls=write_bytes("sheet.xls", b"legacy-excel"),
        pptx=write_bytes("slides.pptx", b"PK\x03\x04fake-pptx"),
        odt=write_bytes("document.odt", b"PK\x03\x04fake-odt"),
        ods=write_bytes("spreadsheet.ods", b"PK\x03\x04fake-ods"),
        odp=write_bytes("presentation.odp", b"PK\x03\x04fake-odp"),
        pages=write_bytes("proposal.pages", b"pages-data"),
        numbers=write_bytes("budget.numbers", b"numbers-data"),
        key=write_bytes("deck.key", b"keynote-data"),
        rtf=write_text("sample.rtf", r"{\rtf1\ansi Sample \b RTF\b0\par }"),
        unsupported=write_text("notes.txt", "ignore me"),
        empty_docx=write_bytes("empty.docx", b""),
        corrupted_docx=write_bytes("corrupted.docx", b"\x00\xffcorrupt"),
        large_docx=write_bytes("large.docx", b"L" * (1024 * 1024)),
        nested_docx=write_bytes("nested/inside.docx", b"nested-docx"),
        nested_xlsx=write_bytes("nested/inside.xlsx", b"nested-xlsx"),
        nested_pptx=write_bytes("nested/inside.pptx", b"nested-pptx"),
    )


@pytest.fixture
def sample_paragraph(office_modules):
    """Create a paragraph fixture with a single run."""
    style = office_modules.models.DocumentStyle(font_family="Arial", bold=True)
    run = office_modules.models.TextRun(text="Hello office", style=style, language="en")
    return office_modules.models.Paragraph(
        runs=[run],
        style=style,
        paragraph_id="p-1",
        is_heading=True,
        heading_level=1,
    )


@pytest.fixture
def sample_table(office_modules, sample_paragraph):
    """Create a simple table fixture."""
    cell = office_modules.models.TableCell(paragraphs=[sample_paragraph], colspan=2)
    return office_modules.models.Table(
        rows=[[cell]],
        has_header_row=True,
        cell_grid={"A1": cell},
        captions=[sample_paragraph],
    )


@pytest.fixture
def sample_image(office_modules):
    """Create a representative image fixture."""
    return office_modules.models.Image(
        data=b"\x89PNG\r\n",
        mime_type="image/png",
        description="Accessible chart image",
        title="Chart",
        alternate_text="Quarterly revenue chart",
        anchor_paragraph="p-1",
        position={"x": 10.0, "y": 15.0},
        properties={"decorative": False},
    )
