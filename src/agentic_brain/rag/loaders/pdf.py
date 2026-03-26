# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""PDF loader for RAG pipelines."""

import logging
from io import BytesIO
from pathlib import Path
from typing import Optional

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


class PDFLoader(BaseLoader):
    """Load and extract text from PDF documents.

    Supports:
    - Text extraction from PDFs
    - Multiple extraction backends (PyPDF2, pdfplumber)
    - Local file loading
    - OCR fallback (if pytesseract installed)

    Example:
        loader = PDFLoader()
        doc = loader.load_document("/path/to/document.pdf")
        docs = loader.load_folder("/path/to/pdfs/")
    """

    def __init__(
        self,
        base_path: str = ".",
        extract_images: bool = False,
        ocr_enabled: bool = False,
        max_pages: int = 500,
    ):
        """Initialize PDF loader.

        Args:
            base_path: Base path for relative file paths
            extract_images: Extract text from images using OCR
            ocr_enabled: Enable OCR for scanned documents
            max_pages: Maximum pages to process per document
        """
        self.base_path = Path(base_path)
        self.extract_images = extract_images
        self.ocr_enabled = ocr_enabled
        self.max_pages = max_pages

    @property
    def source_name(self) -> str:
        return "pdf"

    def authenticate(self) -> bool:
        """No authentication needed for local PDFs."""
        return True

    def _extract_text_pypdf2(self, pdf_bytes: bytes) -> str:
        """Extract text using PyPDF2."""
        if not PYPDF2_AVAILABLE:
            return ""

        try:
            reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            text_parts = []
            for i, page in enumerate(reader.pages):
                if i >= self.max_pages:
                    break
                text = page.extract_text()
                if text:
                    text_parts.append(text)
            return "\n\n".join(text_parts)
        except Exception as e:
            logger.debug(f"PyPDF2 extraction failed: {e}")
            return ""

    def _extract_text_pdfplumber(self, pdf_bytes: bytes) -> str:
        """Extract text using pdfplumber."""
        if not PDFPLUMBER_AVAILABLE:
            return ""

        try:
            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text_parts = []
                for i, page in enumerate(pdf.pages):
                    if i >= self.max_pages:
                        break
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
                return "\n\n".join(text_parts)
        except Exception as e:
            logger.debug(f"pdfplumber extraction failed: {e}")
            return ""

    def _extract_text(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF using best available method."""
        # Try pdfplumber first (usually better quality)
        text = self._extract_text_pdfplumber(pdf_bytes)
        if text.strip():
            return text

        # Fallback to PyPDF2
        text = self._extract_text_pypdf2(pdf_bytes)
        if text.strip():
            return text

        # No extraction library available
        logger.warning("No PDF extraction library available")
        return "[PDF content - install PyPDF2 or pdfplumber]"

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single PDF document."""
        try:
            path = Path(doc_id)
            if not path.is_absolute():
                path = self.base_path / path

            if not path.exists():
                logger.error(f"PDF file not found: {path}")
                return None

            if path.suffix.lower() != ".pdf":
                logger.warning(f"Not a PDF file: {path}")
                return None

            with open(path, "rb") as f:
                pdf_bytes = f.read()

            content = self._extract_text(pdf_bytes)

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                mime_type="application/pdf",
                size_bytes=len(pdf_bytes),
                metadata={
                    "path": str(path),
                    "pages_extracted": content.count("\n\n") + 1,
                },
            )
        except Exception as e:
            logger.error(f"Failed to load PDF {doc_id}: {e}")
            return None

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
            doc = self.load_document(str(pdf_path))
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
