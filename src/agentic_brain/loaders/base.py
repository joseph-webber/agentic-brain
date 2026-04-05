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

"""Base document loader interface and utilities."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Represents a loaded document with metadata."""

    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    source: Optional[str] = None
    loaded_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self) -> None:
        """Ensure metadata is a dict."""
        if not isinstance(self.metadata, dict):
            self.metadata = {}

    def to_dict(self) -> dict[str, Any]:
        """Convert document to dictionary."""
        return {
            "content": self.content,
            "metadata": self.metadata,
            "source": self.source,
            "loaded_at": self.loaded_at.isoformat(),
        }


class DocumentLoader(ABC):
    """Abstract base class for document loaders."""

    @abstractmethod
    async def load(self, source: str | Path) -> list[Document]:
        """
        Load document(s) from source.

        Args:
            source: Path to file or resource identifier

        Returns:
            List of loaded documents

        Raises:
            FileNotFoundError: If source doesn't exist
            ValueError: If source format is invalid
        """

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.pdf', '.txt'])."""

    def can_load(self, source: str | Path) -> bool:
        """Check if this loader can load the given source."""
        path = Path(source)
        return path.suffix.lower() in self.supported_extensions()


class SyncDocumentLoader(DocumentLoader):
    """Synchronous document loader base class."""

    async def load(self, source: str | Path) -> list[Document]:
        """Load documents using sync method."""
        return self.load_sync(source)

    @abstractmethod
    def load_sync(self, source: str | Path) -> list[Document]:
        """Synchronous load implementation."""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions."""


class TextLoader(SyncDocumentLoader):
    """Load plain text files."""

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load text file."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            return [
                Document(
                    content=content,
                    source=str(path),
                    metadata={"filename": path.name, "size": path.stat().st_size},
                )
            ]
        except Exception as e:
            logger.error(f"Error loading text file {path}: {e}")
            raise ValueError(f"Failed to load text file: {e}") from e

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".txt", ".md", ".py", ".js", ".ts", ".java", ".go", ".rs"]
