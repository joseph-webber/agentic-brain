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

"""Base loader class and common utilities for RAG document loaders."""

import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

# Type variable for retry decorator
T = TypeVar("T")


class RateLimitError(Exception):
    """Raised when rate limit is hit."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


def with_rate_limit(
    requests_per_minute: int = 60,
    retry_count: int = 3,
    backoff_factor: float = 2.0,
) -> Callable:
    """Decorator to add rate limiting to loader methods.

    Args:
        requests_per_minute: Max requests per minute
        retry_count: Number of retries on rate limit
        backoff_factor: Multiplier for exponential backoff

    Example:
        @with_rate_limit(requests_per_minute=30)
        def load_document(self, doc_id: str) -> LoadedDocument:
            ...
    """
    # Simple token bucket state (per-decorated-function)
    state = {"tokens": requests_per_minute, "last_refill": time.time()}
    min_interval = 60.0 / requests_per_minute

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            nonlocal state

            # Refill tokens based on elapsed time
            now = time.time()
            elapsed = now - state["last_refill"]
            refill = int(elapsed / min_interval)
            if refill > 0:
                state["tokens"] = min(requests_per_minute, state["tokens"] + refill)
                state["last_refill"] = now

            # Wait if no tokens
            if state["tokens"] <= 0:
                wait_time = min_interval - (now - state["last_refill"])
                if wait_time > 0:
                    logger.debug(f"Rate limit: waiting {wait_time:.2f}s")
                    time.sleep(wait_time)
                state["tokens"] = 1
                state["last_refill"] = time.time()

            # Try with retries
            last_error = None
            for attempt in range(retry_count + 1):
                try:
                    state["tokens"] -= 1
                    return func(*args, **kwargs)
                except Exception as e:
                    # Check if rate limit error (429)
                    if "429" in str(e) or "rate" in str(e).lower():
                        wait = backoff_factor**attempt
                        logger.warning(
                            f"Rate limited, retry {attempt+1}/{retry_count} in {wait}s"
                        )
                        time.sleep(wait)
                        last_error = e
                    else:
                        raise

            raise RateLimitError() from last_error

        return wrapper

    return decorator


def _validate_sql_identifier(name: str) -> str:
    """Validate and return a safe SQL identifier (table/column name).

    Args:
        name: The identifier to validate

    Returns:
        The validated identifier

    Raises:
        ValueError: If the identifier contains unsafe characters
    """
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


def _validate_salesforce_object(name: str) -> str:
    """Validate Salesforce object name (allows custom objects with __c suffix)."""
    if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*(__c)?$", name):
        raise ValueError(f"Invalid Salesforce object name: {name}")
    return name


@dataclass
class LoadedDocument:
    """A document loaded from a source."""

    content: str
    id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    source: str = ""  # e.g., "google_drive", "gmail", "local"
    source_id: str = ""  # Original ID in the source system
    filename: str = ""
    mime_type: str = "text/plain"
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    size_bytes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize document to dictionary."""
        return {
            "content": self.content,
            "id": self.id,
            "metadata": self.metadata,
            "source": self.source,
            "source_id": self.source_id,
            "filename": self.filename,
            "mime_type": self.mime_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat() if self.modified_at else None,
            "size_bytes": self.size_bytes,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LoadedDocument":
        """Create document from dictionary."""
        created_at = None
        modified_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])
        if data.get("modified_at"):
            modified_at = datetime.fromisoformat(data["modified_at"])

        return cls(
            content=data.get("content", ""),
            id=data.get("id", ""),
            metadata=data.get("metadata", {}),
            source=data.get("source", ""),
            source_id=data.get("source_id", ""),
            filename=data.get("filename", ""),
            mime_type=data.get("mime_type", "text/plain"),
            created_at=created_at,
            modified_at=modified_at,
            size_bytes=data.get("size_bytes", 0),
        )


class BaseLoader(ABC):
    """Abstract base class for document loaders.

    Supports context manager protocol for proper resource cleanup:

        with S3Loader(bucket="my-bucket") as loader:
            docs = loader.load_folder("documents/")
        # Connection automatically closed
    """

    def __enter__(self) -> "BaseLoader":
        """Enter context manager - authenticate and setup."""
        self.authenticate()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager - cleanup resources."""
        self.close()
        return None

    def close(self) -> None:
        """Close connections and cleanup resources. Override in subclasses."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the source (e.g., 'google_drive', 'local')."""
        pass

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the service. Returns True if successful."""
        pass

    @abstractmethod
    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single document by ID."""
        pass

    @abstractmethod
    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a folder."""
        pass

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for documents.

        Subclasses can override this. The default implementation returns no
        results so loaders remain instantiable when search is optional.
        """
        return []

    def load(self) -> list[LoadedDocument]:
        """Backward-compatible convenience method used by CI tests."""
        base_path = getattr(self, "base_path", None)
        if base_path is None:
            return []

        path = Path(base_path)
        if path.is_file():
            doc = self.load_document(str(path))
            return [doc] if doc else []
        if path.is_dir():
            return self.load_folder(".", recursive=True)

        doc = self.load_document(str(path))
        return [doc] if doc else []

    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF bytes. Tries multiple methods."""
        # Try PyPDF2
        try:
            from io import BytesIO

            import PyPDF2

            reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
            if text.strip():
                return text.strip()
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"PyPDF2 extraction failed: {e}")

        # Try pdfplumber
        try:
            from io import BytesIO

            import pdfplumber

            with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
                text = ""
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
            if text.strip():
                return text.strip()
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"pdfplumber extraction failed: {e}")

        logger.warning(
            "No PDF extraction library available. Install PyPDF2 or pdfplumber."
        )
        return "[PDF content - extraction library not available]"

    def _clean_html(self, html: str) -> str:
        """Convert HTML to plain text."""
        # Try BeautifulSoup
        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "html.parser")
            # Remove script and style elements
            for element in soup(["script", "style", "head", "meta", "link"]):
                element.decompose()
            text = soup.get_text(separator="\n")
            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            return "\n".join(line for line in lines if line)
        except ImportError:
            pass

        # Fallback: basic regex
        text = re.sub(
            r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


__all__ = [
    "BaseLoader",
    "LoadedDocument",
    "RateLimitError",
    "with_rate_limit",
    "_validate_sql_identifier",
    "_validate_salesforce_object",
]
