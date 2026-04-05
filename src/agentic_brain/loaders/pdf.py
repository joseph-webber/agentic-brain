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

"""PDF document loader."""

import logging
from pathlib import Path
from typing import Optional

from .base import Document, SyncDocumentLoader

logger = logging.getLogger(__name__)


class PDFLoader(SyncDocumentLoader):
    """Load PDF files using pypdf."""

    def __init__(self, extract_metadata: bool = True):
        """Initialize PDF loader.

        Args:
            extract_metadata: Whether to extract PDF metadata
        """
        self.extract_metadata = extract_metadata

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load PDF file."""
        try:
            import pypdf
        except ImportError:
            raise ImportError(
                "pypdf not installed. Install with: pip install pypdf"
            ) from None

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        documents = []
        try:
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                num_pages = len(reader.pages)

                metadata = {}
                if self.extract_metadata and reader.metadata:
                    metadata = {
                        "title": reader.metadata.get("/Title", ""),
                        "author": reader.metadata.get("/Author", ""),
                        "subject": reader.metadata.get("/Subject", ""),
                        "creator": reader.metadata.get("/Creator", ""),
                    }

                full_text = ""
                for page_num, page in enumerate(reader.pages, 1):
                    try:
                        text = page.extract_text()
                        full_text += f"\n--- Page {page_num} ---\n{text}"
                    except Exception as e:
                        logger.warning(
                            f"Error extracting text from page {page_num}: {e}"
                        )

                if full_text.strip():
                    documents.append(
                        Document(
                            content=full_text,
                            source=str(path),
                            metadata={
                                "filename": path.name,
                                "num_pages": num_pages,
                                "size": path.stat().st_size,
                                **metadata,
                            },
                        )
                    )

        except Exception as e:
            logger.error(f"Error loading PDF {path}: {e}")
            raise ValueError(f"Failed to load PDF: {e}") from e

        return documents

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".pdf"]


class PDFPageLoader(SyncDocumentLoader):
    """Load PDF files, creating separate document per page."""

    def __init__(self, extract_metadata: bool = True):
        """Initialize PDF page loader.

        Args:
            extract_metadata: Whether to extract PDF metadata
        """
        self.extract_metadata = extract_metadata

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load PDF file, one document per page."""
        try:
            import pypdf
        except ImportError:
            raise ImportError(
                "pypdf not installed. Install with: pip install pypdf"
            ) from None

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"PDF file not found: {path}")

        documents = []
        try:
            with open(path, "rb") as f:
                reader = pypdf.PdfReader(f)
                num_pages = len(reader.pages)

                pdf_metadata = {}
                if self.extract_metadata and reader.metadata:
                    pdf_metadata = {
                        "title": reader.metadata.get("/Title", ""),
                        "author": reader.metadata.get("/Author", ""),
                        "subject": reader.metadata.get("/Subject", ""),
                        "creator": reader.metadata.get("/Creator", ""),
                    }

                for page_num, page in enumerate(reader.pages, 1):
                    try:
                        text = page.extract_text()
                        if text.strip():
                            documents.append(
                                Document(
                                    content=text,
                                    source=str(path),
                                    metadata={
                                        "filename": path.name,
                                        "page": page_num,
                                        "total_pages": num_pages,
                                        "size": path.stat().st_size,
                                        **pdf_metadata,
                                    },
                                )
                            )
                    except Exception as e:
                        logger.warning(
                            f"Error extracting text from page {page_num}: {e}"
                        )

        except Exception as e:
            logger.error(f"Error loading PDF {path}: {e}")
            raise ValueError(f"Failed to load PDF: {e}") from e

        return documents

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".pdf"]
