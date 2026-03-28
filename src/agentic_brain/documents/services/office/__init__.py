# SPDX-License-Identifier: Apache-2.0

"""
Office document services for agentic-brain.

Provides conversion services for office document formats including
Microsoft Office, Apple iWork, and OpenDocument formats.
"""

from .api import (
    DocumentContent,
    check_accessibility,
    convert_format,
    convert_to_pdf,
    convert_to_text,
    extract_images,
    extract_tables,
    extract_text,
    load_for_rag,
    process_directory,
    process_excel,
    process_keynote,
    process_numbers,
    process_office_document,
    process_pages,
    process_powerpoint,
    process_word,
    redact_document,
    remediate_accessibility,
    scan_for_pii,
    scrub_metadata,
)
from .converter import ConversionError, OfficeConverter, OfficeFormat
from .security import OfficeSecurityService
from .accessibility import (
    ContrastFix,
    OfficeAccessibilityProcessor,
    ReadingOrderReport,
    Suggestion,
    WCAGReport,
)
from .rag_loaders import (
    UnifiedOfficeLoader,
    WordRAGLoader,
    ExcelRAGLoader,
    PowerPointRAGLoader,
    PagesRAGLoader,
    NumbersRAGLoader,
    KeynoteRAGLoader,
    OpenDocumentRAGLoader,
    register_office_loaders,
    load_office_document,
    load_office_directory,
    load_and_chunk_office,
)
from .pipeline import (
    OfficeDocumentPipeline,
    OfficeDocumentResult,
    BatchProcessingResult,
    SecurityScanResult as PipelineSecurityScanResult,
    PipelineError,
)

__all__ = [
    "ContrastFix",
    "OfficeConverter",
    "OfficeAccessibilityProcessor",
    "OfficeFormat",
    "ReadingOrderReport",
    "Suggestion",
    "WCAGReport",
    "ConversionError",
    "OfficeSecurityService",
    # Public API
    "DocumentContent",
    "process_office_document",
    "process_word",
    "process_excel",
    "process_powerpoint",
    "process_pages",
    "process_numbers",
    "process_keynote",
    "extract_text",
    "extract_tables",
    "extract_images",
    "convert_to_pdf",
    "convert_to_text",
    "convert_format",
    "scan_for_pii",
    "redact_document",
    "scrub_metadata",
    "check_accessibility",
    "remediate_accessibility",
    "load_for_rag",
    "process_directory",
    # RAG Loaders
    "UnifiedOfficeLoader",
    "WordRAGLoader",
    "ExcelRAGLoader",
    "PowerPointRAGLoader",
    "PagesRAGLoader",
    "NumbersRAGLoader",
    "KeynoteRAGLoader",
    "OpenDocumentRAGLoader",
    "register_office_loaders",
    "load_office_document",
    "load_office_directory",
    "load_and_chunk_office",
    # Pipeline
    "OfficeDocumentPipeline",
    "OfficeDocumentResult",
    "BatchProcessingResult",
    "PipelineSecurityScanResult",
    "PipelineError",
]
