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
