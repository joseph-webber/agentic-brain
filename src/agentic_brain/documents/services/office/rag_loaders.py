# SPDX-License-Identifier: Apache-2.0

"""
Unified RAG loaders for office documents.

Integrates office processors with the RAG system, providing seamless loading,
chunking, and embedding of Word, Excel, PowerPoint, Pages, Numbers, Keynote,
and OpenDocument formats.

Implements the BaseLoader interface for compatibility with the existing RAG
loader factory and provides format-specific loaders with intelligent chunking.
"""

import logging
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import Any, Iterator, Optional

from ...rag.chunking import BaseChunker, ChunkingStrategy, create_chunker
from ...rag.loaders.base import BaseLoader, LoadedDocument
from .apple_keynote import KeynoteProcessor
from .apple_numbers import NumbersProcessor
from .apple_pages import PagesProcessor
from .converter import OfficeConverter
from .excel import ExcelProcessor
from .models import DocumentContent, OfficeFormat, Paragraph, Slide, Table, Worksheet
from .opendocument import OpenDocumentProcessor
from .powerpoint import PowerPointProcessor
from .word import WordProcessor

logger = logging.getLogger(__name__)


# ============================================================================
# Helper Functions
# ============================================================================


def _format_paragraph(paragraph: Paragraph) -> str:
    """Format paragraph with basic markdown styling."""
    text = paragraph.text_content()
    
    if paragraph.is_heading and paragraph.heading_level:
        # Add markdown heading
        prefix = "#" * paragraph.heading_level
        return f"{prefix} {text}"
    
    return text


def _format_table(table: Table, max_rows: int = 100) -> str:
    """Format table as markdown."""
    if not table.rows:
        return ""
    
    lines = []
    lines.append("\n**Table:**\n")
    
    # Process rows (limit to max_rows)
    for i, row in enumerate(table.rows[:max_rows]):
        if i == 0:
            # Header row
            cells = [cell.text_content() for cell in row.cells]
            lines.append("| " + " | ".join(cells) + " |")
            lines.append("| " + " | ".join(["---"] * len(cells)) + " |")
        else:
            # Data rows
            cells = [cell.text_content() for cell in row.cells]
            lines.append("| " + " | ".join(cells) + " |")
    
    if len(table.rows) > max_rows:
        lines.append(f"\n*(Table truncated - showing {max_rows} of {len(table.rows)} rows)*\n")
    
    return "\n".join(lines)


def _format_slide(slide: Slide, slide_number: int) -> str:
    """Format slide content with structure."""
    lines = [f"\n## Slide {slide_number}: {slide.title or 'Untitled'}\n"]
    
    # Add content paragraphs
    for paragraph in slide.content:
        lines.append(_format_paragraph(paragraph))
    
    # Add tables
    for table in slide.tables:
        lines.append(_format_table(table, max_rows=50))
    
    # Add notes
    if slide.notes:
        lines.append("\n**Speaker Notes:**")
        for note in slide.notes:
            lines.append(_format_paragraph(note))
    
    return "\n".join(lines)


def _format_worksheet(worksheet: Worksheet, max_rows: int = 1000) -> str:
    """Format worksheet as structured text."""
    lines = [f"\n## Sheet: {worksheet.name}\n"]
    
    if not worksheet.rows:
        lines.append("*(Empty sheet)*")
        return "\n".join(lines)
    
    # Format as table with row numbers
    for i, row in enumerate(worksheet.rows[:max_rows], 1):
        cells = [str(cell.value) if cell.value is not None else "" for cell in row.cells]
        lines.append(f"Row {i}: " + " | ".join(cells))
    
    if len(worksheet.rows) > max_rows:
        lines.append(f"\n*(Worksheet truncated - showing {max_rows} of {len(worksheet.rows)} rows)*")
    
    return "\n".join(lines)


def _extract_text_from_content(content: DocumentContent) -> str:
    """Extract unified text from DocumentContent."""
    parts = []
    
    # Extract paragraphs (Word, Pages, ODT)
    if content.paragraphs:
        for para in content.paragraphs:
            formatted = _format_paragraph(para)
            if formatted.strip():
                parts.append(formatted)
    
    # Extract tables (all formats)
    if content.tables:
        for table in content.tables:
            parts.append(_format_table(table))
    
    # Extract slides (PowerPoint, Keynote, ODP)
    if content.slides:
        for i, slide in enumerate(content.slides, 1):
            parts.append(_format_slide(slide, i))
    
    # Extract worksheets (Excel, Numbers, ODS)
    if content.worksheets:
        for worksheet in content.worksheets:
            parts.append(_format_worksheet(worksheet))
    
    return "\n\n".join(parts)


def _build_metadata(content: DocumentContent, path: Path) -> dict[str, Any]:
    """Build comprehensive metadata from DocumentContent."""
    metadata = {
        "source_path": str(path),
        "filename": path.name,
        "format": content.format.value,
        "file_extension": path.suffix,
    }
    
    # Add document metadata
    if content.metadata:
        if content.metadata.title:
            metadata["title"] = content.metadata.title
        if content.metadata.author:
            metadata["author"] = content.metadata.author
        if content.metadata.subject:
            metadata["subject"] = content.metadata.subject
        if content.metadata.keywords:
            metadata["keywords"] = ", ".join(content.metadata.keywords)
        if content.metadata.created_at:
            metadata["created_at"] = content.metadata.created_at.isoformat()
        if content.metadata.modified_at:
            metadata["modified_at"] = content.metadata.modified_at.isoformat()
        if content.metadata.company:
            metadata["company"] = content.metadata.company
    
    # Add content statistics
    metadata["paragraph_count"] = len(content.paragraphs)
    metadata["table_count"] = len(content.tables)
    metadata["image_count"] = len(content.images)
    metadata["slide_count"] = len(content.slides)
    metadata["worksheet_count"] = len(content.worksheets)
    
    return metadata


# ============================================================================
# Unified Office Loader
# ============================================================================


class UnifiedOfficeLoader(BaseLoader):
    """
    Unified loader for all office document formats.
    
    Automatically detects format and uses appropriate processor.
    Supports Word, Excel, PowerPoint, Pages, Numbers, Keynote, and OpenDocument.
    
    Example:
        >>> loader = UnifiedOfficeLoader(base_path="/documents")
        >>> doc = loader.load_document("report.docx")
        >>> docs = loader.load_folder("reports/", recursive=True)
        >>> chunked = loader.load_and_chunk("presentation.pptx", chunk_size=512)
    """
    
    # Supported formats mapping
    SUPPORTED_FORMATS = {
        ".docx": (WordProcessor, OfficeFormat.DOCX),
        ".xlsx": (ExcelProcessor, OfficeFormat.XLSX),
        ".pptx": (PowerPointProcessor, OfficeFormat.PPTX),
        ".pages": (PagesProcessor, OfficeFormat.PAGES),
        ".numbers": (NumbersProcessor, OfficeFormat.NUMBERS),
        ".keynote": (KeynoteProcessor, OfficeFormat.KEYNOTE),
        ".key": (KeynoteProcessor, OfficeFormat.KEYNOTE),
        ".odt": (OpenDocumentProcessor, OfficeFormat.ODT),
        ".ods": (OpenDocumentProcessor, OfficeFormat.ODS),
        ".odp": (OpenDocumentProcessor, OfficeFormat.ODP),
    }
    
    def __init__(
        self,
        base_path: str = ".",
        max_table_rows: int = 100,
        max_worksheet_rows: int = 1000,
        include_images: bool = False,
    ):
        """
        Initialize unified office loader.
        
        Args:
            base_path: Base directory for relative paths
            max_table_rows: Maximum rows to extract from tables
            max_worksheet_rows: Maximum rows to extract from worksheets
            include_images: Include image descriptions in content
        """
        self.base_path = Path(base_path)
        self.max_table_rows = max_table_rows
        self.max_worksheet_rows = max_worksheet_rows
        self.include_images = include_images
    
    @property
    def source_name(self) -> str:
        """Return source identifier."""
        return "office"
    
    def authenticate(self) -> bool:
        """Authenticate (always True for local files)."""
        return True
    
    def supports_format(self, path: Path | str) -> bool:
        """Check if file format is supported."""
        path = Path(path)
        return path.suffix.lower() in self.SUPPORTED_FORMATS
    
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """
        Load single office document by path.
        
        Args:
            doc_id: Path to document (absolute or relative to base_path)
        
        Returns:
            LoadedDocument with extracted content and metadata
        """
        path = Path(doc_id)
        if not path.is_absolute():
            path = self.base_path / path
        
        if not path.exists():
            logger.warning(f"Document not found: {path}")
            return None
        
        if not self.supports_format(path):
            logger.warning(f"Unsupported format: {path.suffix}")
            return None
        
        try:
            # Get processor for format
            processor_class, office_format = self.SUPPORTED_FORMATS[path.suffix.lower()]
            
            if processor_class is None:
                logger.warning(f"Processor not yet implemented for {path.suffix}")
                return None
            
            # Process document
            processor = processor_class()
            content = processor.parse(path)
            
            # Extract text
            text_content = _extract_text_from_content(content)
            
            # Build metadata
            metadata = _build_metadata(content, path)
            
            # Get file stats
            stats = path.stat()
            
            return LoadedDocument(
                content=text_content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                mime_type=self._get_mime_type(path.suffix),
                metadata=metadata,
                size_bytes=stats.st_size,
            )
        
        except Exception as e:
            logger.error(f"Failed to load {path}: {e}", exc_info=True)
            return None
    
    def load_folder(
        self, 
        folder_path: str, 
        recursive: bool = True
    ) -> list[LoadedDocument]:
        """
        Load all supported office documents from folder.
        
        Args:
            folder_path: Path to folder (absolute or relative to base_path)
            recursive: Search subdirectories
        
        Returns:
            List of loaded documents
        """
        path = Path(folder_path)
        if not path.is_absolute():
            path = self.base_path / path
        
        if not path.exists() or not path.is_dir():
            logger.warning(f"Folder not found: {path}")
            return []
        
        docs = []
        
        # Find all supported documents
        for ext in self.SUPPORTED_FORMATS.keys():
            pattern = f"**/*{ext}" if recursive else f"*{ext}"
            for doc_path in path.glob(pattern):
                doc = self.load_document(str(doc_path))
                if doc:
                    docs.append(doc)
        
        logger.info(f"Loaded {len(docs)} documents from {path}")
        return docs
    
    def load_multiple(self, paths: list[str | Path]) -> list[LoadedDocument]:
        """
        Load multiple documents by path.
        
        Args:
            paths: List of document paths
        
        Returns:
            List of loaded documents
        """
        docs = []
        for path in paths:
            doc = self.load_document(str(path))
            if doc:
                docs.append(doc)
        return docs
    
    def load_and_chunk(
        self,
        path: str | Path,
        chunk_size: int = 512,
        overlap: int = 50,
        strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC,
    ) -> list[LoadedDocument]:
        """
        Load document and split into chunks.
        
        Args:
            path: Path to document
            chunk_size: Target chunk size in characters
            overlap: Character overlap between chunks
            strategy: Chunking strategy to use
        
        Returns:
            List of LoadedDocument objects, one per chunk
        """
        # Load full document
        doc = self.load_document(str(path))
        if not doc:
            return []
        
        # Create chunker
        chunker = create_chunker(strategy, chunk_size=chunk_size, overlap=overlap)
        
        # Chunk content
        chunks = chunker.chunk(doc.content, metadata=doc.metadata)
        
        # Create LoadedDocument for each chunk
        chunked_docs = []
        for i, chunk in enumerate(chunks):
            chunk_metadata = {
                **doc.metadata,
                "chunk_index": i,
                "chunk_count": len(chunks),
                "chunk_start": chunk.start_char,
                "chunk_end": chunk.end_char,
            }
            
            chunked_doc = LoadedDocument(
                content=chunk.content,
                source=doc.source,
                source_id=f"{doc.source_id}#chunk{i}",
                filename=doc.filename,
                mime_type=doc.mime_type,
                metadata=chunk_metadata,
                size_bytes=len(chunk.content.encode('utf-8')),
            )
            chunked_docs.append(chunked_doc)
        
        return chunked_docs
    
    def _get_mime_type(self, extension: str) -> str:
        """Get MIME type for file extension."""
        mime_types = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".pages": "application/vnd.apple.pages",
            ".numbers": "application/vnd.apple.numbers",
            ".keynote": "application/vnd.apple.keynote",
            ".key": "application/vnd.apple.keynote",
            ".odt": "application/vnd.oasis.opendocument.text",
            ".ods": "application/vnd.oasis.opendocument.spreadsheet",
            ".odp": "application/vnd.oasis.opendocument.presentation",
        }
        return mime_types.get(extension.lower(), "application/octet-stream")


# ============================================================================
# Format-Specific Loaders
# ============================================================================


class WordRAGLoader(UnifiedOfficeLoader):
    """RAG loader specifically for Word documents (.docx)."""
    
    SUPPORTED_FORMATS = {
        ".docx": (WordProcessor, OfficeFormat.DOCX),
    }
    
    @property
    def source_name(self) -> str:
        return "word"


class ExcelRAGLoader(UnifiedOfficeLoader):
    """RAG loader specifically for Excel spreadsheets (.xlsx)."""
    
    SUPPORTED_FORMATS = {
        ".xlsx": (ExcelProcessor, OfficeFormat.XLSX),
    }
    
    @property
    def source_name(self) -> str:
        return "excel"


class PowerPointRAGLoader(UnifiedOfficeLoader):
    """RAG loader specifically for PowerPoint presentations (.pptx)."""
    
    SUPPORTED_FORMATS = {
        ".pptx": (PowerPointProcessor, OfficeFormat.PPTX),
    }
    
    @property
    def source_name(self) -> str:
        return "powerpoint"


class PagesRAGLoader(UnifiedOfficeLoader):
    """RAG loader specifically for Apple Pages documents (.pages)."""
    
    SUPPORTED_FORMATS = {
        ".pages": (PagesProcessor, OfficeFormat.PAGES),
    }
    
    @property
    def source_name(self) -> str:
        return "pages"


class NumbersRAGLoader(UnifiedOfficeLoader):
    """RAG loader specifically for Apple Numbers spreadsheets (.numbers)."""
    
    SUPPORTED_FORMATS = {
        ".numbers": (NumbersProcessor, OfficeFormat.NUMBERS),
    }
    
    @property
    def source_name(self) -> str:
        return "numbers"


class KeynoteRAGLoader(UnifiedOfficeLoader):
    """RAG loader specifically for Apple Keynote presentations (.keynote, .key)."""
    
    SUPPORTED_FORMATS = {
        ".keynote": (KeynoteProcessor, OfficeFormat.KEYNOTE),
        ".key": (KeynoteProcessor, OfficeFormat.KEYNOTE),
    }
    
    @property
    def source_name(self) -> str:
        return "keynote"


class OpenDocumentRAGLoader(UnifiedOfficeLoader):
    """RAG loader for OpenDocument formats (.odt, .ods, .odp)."""
    
    SUPPORTED_FORMATS = {
        ".odt": (OpenDocumentProcessor, OfficeFormat.ODT),
        ".ods": (OpenDocumentProcessor, OfficeFormat.ODS),
        ".odp": (OpenDocumentProcessor, OfficeFormat.ODP),
    }
    
    @property
    def source_name(self) -> str:
        return "opendocument"


# ============================================================================
# Loader Factory Integration
# ============================================================================


def register_office_loaders():
    """
    Register office loaders with the RAG loader factory.
    
    Call this in rag/loaders/factory.py _register_loaders():
        from ...documents.services.office.rag_loaders import register_office_loaders
        register_office_loaders()
    """
    try:
        from ...rag.loaders.factory import _LOADER_REGISTRY
        
        # Register unified loader
        _LOADER_REGISTRY["office"] = UnifiedOfficeLoader
        
        # Register format-specific loaders
        _LOADER_REGISTRY["word"] = WordRAGLoader
        _LOADER_REGISTRY["docx"] = WordRAGLoader
        _LOADER_REGISTRY["excel"] = ExcelRAGLoader
        _LOADER_REGISTRY["xlsx"] = ExcelRAGLoader
        _LOADER_REGISTRY["powerpoint"] = PowerPointRAGLoader
        _LOADER_REGISTRY["pptx"] = PowerPointRAGLoader
        _LOADER_REGISTRY["pages"] = PagesRAGLoader
        _LOADER_REGISTRY["numbers"] = NumbersRAGLoader
        _LOADER_REGISTRY["keynote"] = KeynoteRAGLoader
        _LOADER_REGISTRY["opendocument"] = OpenDocumentRAGLoader
        _LOADER_REGISTRY["odt"] = OpenDocumentRAGLoader
        _LOADER_REGISTRY["ods"] = OpenDocumentRAGLoader
        _LOADER_REGISTRY["odp"] = OpenDocumentRAGLoader
        
        logger.info("Registered office loaders with RAG factory")
        return True
    
    except ImportError as e:
        logger.warning(f"Could not register office loaders: {e}")
        return False


# ============================================================================
# Convenience Functions
# ============================================================================


def load_office_document(path: str | Path, **kwargs) -> Optional[LoadedDocument]:
    """
    Load any supported office document.
    
    Args:
        path: Path to document
        **kwargs: Additional loader options
    
    Returns:
        LoadedDocument or None
    """
    loader = UnifiedOfficeLoader(**kwargs)
    return loader.load_document(str(path))


def load_office_directory(
    directory: str | Path,
    recursive: bool = True,
    **kwargs
) -> list[LoadedDocument]:
    """
    Load all office documents from directory.
    
    Args:
        directory: Path to directory
        recursive: Search subdirectories
        **kwargs: Additional loader options
    
    Returns:
        List of LoadedDocument objects
    """
    loader = UnifiedOfficeLoader(**kwargs)
    return loader.load_folder(str(directory), recursive=recursive)


def load_and_chunk_office(
    path: str | Path,
    chunk_size: int = 512,
    overlap: int = 50,
    strategy: ChunkingStrategy = ChunkingStrategy.SEMANTIC,
    **kwargs
) -> list[LoadedDocument]:
    """
    Load office document and split into chunks.
    
    Args:
        path: Path to document
        chunk_size: Target chunk size in characters
        overlap: Character overlap between chunks
        strategy: Chunking strategy
        **kwargs: Additional loader options
    
    Returns:
        List of chunked LoadedDocument objects
    """
    loader = UnifiedOfficeLoader(**kwargs)
    return loader.load_and_chunk(path, chunk_size=chunk_size, overlap=overlap, strategy=strategy)
