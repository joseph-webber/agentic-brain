# SPDX-License-Identifier: Apache-2.0

"""Custom exceptions for office document services."""

from __future__ import annotations

from typing import Optional

from .models import OfficeFormat


class DocumentModelError(Exception):
    """Base exception for document model issues."""


class InvalidDocumentStructureError(DocumentModelError):
    """Raised when document content is inconsistent or malformed."""

    def __init__(self, message: str, element_id: Optional[str] = None) -> None:
        self.element_id = element_id
        if element_id:
            message = f"{message} (element: {element_id})"
        super().__init__(message)


class UnsupportedOfficeFormatError(DocumentModelError):
    """Raised when a requested office format is not supported."""

    def __init__(self, format_requested: OfficeFormat | str) -> None:
        super().__init__(f"Unsupported office format: {format_requested}")
        self.format_requested = format_requested


class DocumentValidationError(DocumentModelError):
    """Raised when document validation fails before processing."""

    def __init__(self, message: str, details: Optional[str] = None) -> None:
        if details:
            message = f"{message}: {details}"
        super().__init__(message)
        self.details = details
