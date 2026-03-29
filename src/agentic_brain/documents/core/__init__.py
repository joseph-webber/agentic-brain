# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 ("License");
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

"""Document core models and types."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import List, Optional


class DocumentType(Enum):
    PDF = "pdf"
    POSTSCRIPT = "ps"
    LATEX = "latex"
    EPUB = "epub"
    WORD = "docx"
    SCANNED = "scanned"
    PAGES = "pages"
    NUMBERS = "numbers"
    KEYNOTE = "keynote"
    ODF = "odf"
    RTF = "rtf"
    EXCEL = "xlsx"
    POWERPOINT = "pptx"
    GOOGLE_DOC = "google_doc"


@dataclass
class BoundingBox:
    x0: float
    y0: float
    x1: float
    y1: float
    page: int = 0


@dataclass
class ImageInfo:
    path: str
    width: int = 0
    height: int = 0
    format: str = ""
    alt_text: str = ""


@dataclass
class TextBlock:
    text: str
    bbox: Optional[BoundingBox] = None
    style: str = ""
    level: int = 0


@dataclass
class Table:
    rows: List[List[str]] = field(default_factory=list)
    headers: List[str] = field(default_factory=list)
    bbox: Optional[BoundingBox] = None


@dataclass
class PageResult:
    page_number: int
    text: str = ""
    blocks: List[TextBlock] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    images: List[ImageInfo] = field(default_factory=list)


@dataclass
class DocumentMetadata:
    title: str = ""
    author: str = ""
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    page_count: int = 0
    word_count: int = 0
    doc_type: DocumentType = DocumentType.PDF
    file_path: Optional[Path] = None


@dataclass
class DocumentResult:
    metadata: DocumentMetadata = field(default_factory=DocumentMetadata)
    pages: List[PageResult] = field(default_factory=list)
    full_text: str = ""
    success: bool = True
    error: str = ""
