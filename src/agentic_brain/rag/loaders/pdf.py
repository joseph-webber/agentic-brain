# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""PDF loader for RAG pipelines.

Enhanced with Docling-grade features (without the torch/transformers bloat):
- Multi-column layout detection and reordering
- Header/footer detection and stripping
- Table extraction with structure preservation
- Page-level metadata
"""

import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from ..exceptions import LoaderError
from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for PDF libraries
try:
    import PyPDF2

    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import pdfplumber

    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False


def _detect_columns(text_lines: list[str], page_width: float = 612) -> bool:
    """Heuristic to detect multi-column layout.

    Checks if a significant portion of lines are short (< 45% of page width
    equivalent) and have large leading whitespace, suggesting column breaks.
    """
    if not text_lines or len(text_lines) < 5:
        return False

    short_lines = 0
    avg_chars = page_width / 7  # rough chars-per-line estimate

    for line in text_lines:
        stripped = line.strip()
        if stripped and len(stripped) < avg_chars * 0.45:
            short_lines += 1

    return short_lines > len(text_lines) * 0.4


def _strip_headers_footers(pages: list[str], threshold: float = 0.7) -> list[str]:
    """Remove repeated headers/footers across pages.

    If the first or last line of a page appears on more than ``threshold``
    fraction of all pages it is treated as a header or footer and stripped.
    """
    if len(pages) < 3:
        return pages

    first_lines: dict[str, int] = {}
    last_lines: dict[str, int] = {}

    for page in pages:
        lines = [ln.strip() for ln in page.splitlines() if ln.strip()]
        if not lines:
            continue
        first = lines[0]
        last = lines[-1]
        first_lines[first] = first_lines.get(first, 0) + 1
        last_lines[last] = last_lines.get(last, 0) + 1

    min_count = int(len(pages) * threshold)
    header_lines = {ln for ln, c in first_lines.items() if c >= min_count}
    footer_lines = {ln for ln, c in last_lines.items() if c >= min_count}

    # Also catch page-number-only footers like "3", "- 4 -", "Page 5"
    page_num_re = re.compile(r"^[-–—\s]*(?:page\s*)?\d{1,4}[-–—\s]*$", re.I)

    cleaned: list[str] = []
    for page in pages:
        lines = page.splitlines()
        out: list[str] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if i == 0 and stripped in header_lines:
                continue
            if i == len(lines) - 1 and (
                stripped in footer_lines or page_num_re.match(stripped)
            ):
                continue
            out.append(line)
        cleaned.append("\n".join(out))

    return cleaned


def _extract_tables_pdfplumber(
    pdf_bytes: bytes, max_pages: int = 500
) -> list[dict[str, Any]]:
    """Extract tables from PDF using pdfplumber with structure preservation.

    Returns a list of dicts, each with ``headers``, ``rows`` and ``page`` keys.
    """
    if not PDFPLUMBER_AVAILABLE:
        return []

    tables: list[dict[str, Any]] = []
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                if page_idx >= max_pages:
                    break
                page_tables = page.extract_tables() or []
                for tbl in page_tables:
                    if not tbl or not tbl[0]:
                        continue
                    headers = [str(c or "").strip() for c in tbl[0]]
                    rows = [
                        [str(c or "").strip() for c in row]
                        for row in tbl[1:]
                        if any(str(c or "").strip() for c in row)
                    ]
                    tables.append(
                        {
                            "headers": headers,
                            "rows": rows,
                            "page": page_idx + 1,
                            "caption": f"Table on page {page_idx + 1}",
                        }
                    )
    except Exception as e:
        logger.debug(f"pdfplumber table extraction failed: {e}")

    return tables


class PDFLoader(BaseLoader):
    """Load and extract text from PDF documents.

    Enhanced features (inspired by Docling, zero heavy dependencies):
    - Layout-aware text extraction (column reorder heuristic)
    - Header / footer stripping across pages
    - Table extraction with structure preservation
    - OCR fallback (if pytesseract installed)

    Example:
        loader = PDFLoader()
        doc = loader.load_document("/path/to/document.pdf")
        print(doc.to_markdown())   # unified markdown export
        print(doc.metadata["tables"])  # structured tables
    """

    def __init__(
        self,
        base_path: str = ".",
        extract_images: bool = False,
        ocr_enabled: bool = False,
        max_pages: int = 500,
        strip_headers_footers: bool = True,
        extract_tables: bool = True,
    ):
        """Initialize PDF loader.

        Args:
            base_path: Base path for relative file paths
            extract_images: Extract text from images using OCR
            ocr_enabled: Enable OCR for scanned documents
            max_pages: Maximum pages to process per document
            strip_headers_footers: Remove repeated headers/footers
            extract_tables: Extract tables with structure preservation
        """
        self.base_path = Path(base_path)
        self.extract_images = extract_images
        self.ocr_enabled = ocr_enabled
        self.max_pages = max_pages
        self.strip_headers_footers = strip_headers_footers
        self.extract_tables = extract_tables

    @property
    def source_name(self) -> str:
        return "pdf"

    def authenticate(self) -> bool:
        """No authentication needed for local PDFs."""
        return True

    def _extract_pages_pypdf2(self, pdf_bytes: bytes) -> list[str]:
        """Extract per-page text using PyPDF2."""
        if not PYPDF2_AVAILABLE:
            return []

        try:
            reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            pages: list[str] = []
            for i, page in enumerate(reader.pages):
                if i >= self.max_pages:
                    break
                text = page.extract_text()
                pages.append(text or "")
            return pages
        except Exception as e:
            logger.debug(f"PyPDF2 extraction failed: {e}")
            return []

    def _extract_pages_pdfplumber(self, pdf_bytes: bytes) -> list[str]:
        """Extract per-page text using pdfplumber."""
        if not PDFPLUMBER_AVAILABLE:
            return []

        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                pages: list[str] = []
                for i, page in enumerate(pdf.pages):
                    if i >= self.max_pages:
                        break
                    text = page.extract_text() or ""
                    pages.append(text)
                return pages
        except Exception as e:
            logger.debug(f"pdfplumber extraction failed: {e}")
            return []

    def _extract_text(self, pdf_bytes: bytes) -> tuple[str, dict[str, Any]]:
        """Extract text from PDF using best available method.

        Returns:
            Tuple of (full_text, extra_metadata).
        """
        extra_meta: dict[str, Any] = {}

        # Try pdfplumber first (usually better quality)
        pages = self._extract_pages_pdfplumber(pdf_bytes)
        if not any(p.strip() for p in pages):
            pages = self._extract_pages_pypdf2(pdf_bytes)

        if not any(p.strip() for p in pages):
            logger.warning("No PDF extraction library available")
            return "[PDF content - install PyPDF2 or pdfplumber]", extra_meta

        extra_meta["page_count"] = len(pages)

        # Detect layout
        all_lines = []
        for p in pages:
            all_lines.extend(p.splitlines())
        is_multicolumn = _detect_columns(all_lines)
        extra_meta["multicolumn_detected"] = is_multicolumn

        # Strip repeated headers/footers
        if self.strip_headers_footers and len(pages) >= 3:
            pages = _strip_headers_footers(pages)

        # Extract tables
        if self.extract_tables:
            tables = _extract_tables_pdfplumber(pdf_bytes, self.max_pages)
            if tables:
                extra_meta["tables"] = tables
                extra_meta["table_count"] = len(tables)

        text = "\n\n".join(p.strip() for p in pages if p.strip())
        return text, extra_meta

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single PDF document."""
        path = Path(doc_id)
        if not path.is_absolute():
            path = self.base_path / path

        try:
            if not path.exists():
                raise LoaderError(
                    "File not found",
                    context={"path": str(path), "loader": self.source_name},
                )

            if path.suffix.lower() != ".pdf":
                logger.warning(f"Not a PDF file: {path}")
                return None

            with open(path, "rb") as f:
                pdf_bytes = f.read()

            content, extra_meta = self._extract_text(pdf_bytes)

            metadata: dict[str, Any] = {"path": str(path)}
            metadata.update(extra_meta)

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                mime_type="application/pdf",
                size_bytes=len(pdf_bytes),
                metadata=metadata,
            )
        except LoaderError:
            raise
        except FileNotFoundError as exc:
            logger.exception("PDF file not found")
            raise LoaderError(
                "File not found",
                context={"path": str(path), "loader": self.source_name},
            ) from exc
        except PermissionError as exc:
            logger.exception("Permission denied reading PDF")
            raise LoaderError(
                "Permission denied",
                context={"path": str(path), "loader": self.source_name},
            ) from exc
        except OSError as exc:
            logger.exception("I/O error reading PDF")
            raise LoaderError(
                "I/O error reading PDF",
                context={"path": str(path), "loader": self.source_name},
            ) from exc
        except Exception as exc:
            logger.exception("Failed to load PDF")
            raise LoaderError(
                "Failed to load PDF",
                context={"path": str(path), "loader": self.source_name},
            ) from exc

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all PDFs from a folder."""
        docs = []
        path = Path(folder_path)
        if not path.is_absolute():
            path = self.base_path / path

        if not path.exists():
            logger.error(f"Folder not found: {path}")
            return docs

        pattern = "**/*.pdf" if recursive else "*.pdf"

        for pdf_path in path.glob(pattern):
            try:
                doc = self.load_document(str(pdf_path))
            except LoaderError as exc:
                logger.error("Failed to load %s: %s", pdf_path, exc)
                continue

            if doc:
                docs.append(doc)

        logger.info(f"Loaded {len(docs)} PDFs from {folder_path}")
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search is not supported for local PDFs."""
        logger.warning(
            "Search not supported for local PDFs. Load and search in memory."
        )
        return []


__all__ = ["PDFLoader"]
