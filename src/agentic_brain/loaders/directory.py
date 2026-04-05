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

"""Directory loader for batch document loading."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from .base import Document, DocumentLoader
from .csv import CSVLoader
from .docx import DocxLoader
from .html import HTMLLoader
from .json import JSONLinesLoader, JSONLoader
from .markdown import MarkdownLoader
from .pdf import PDFLoader

logger = logging.getLogger(__name__)


class DirectoryLoader:
    """Load all documents from a directory."""

    def __init__(
        self,
        glob_pattern: str = "**/*",
        recursive: bool = True,
        max_workers: int = 4,
    ):
        """Initialize directory loader.

        Args:
            glob_pattern: Glob pattern for files to load (e.g., '*.pdf')
            recursive: Whether to search subdirectories
            max_workers: Number of concurrent loaders
        """
        self.glob_pattern = glob_pattern
        self.recursive = recursive
        self.max_workers = max_workers

        self.loaders: dict[str, DocumentLoader] = {
            ".pdf": PDFLoader(),
            ".docx": DocxLoader(),
            ".html": HTMLLoader(),
            ".htm": HTMLLoader(),
            ".md": MarkdownLoader(),
            ".markdown": MarkdownLoader(),
            ".csv": CSVLoader(),
            ".json": JSONLoader(),
            ".jsonl": JSONLinesLoader(),
            ".ndjson": JSONLinesLoader(),
            ".txt": TextLoader(),
        }

    def add_loader(self, extension: str, loader: DocumentLoader) -> None:
        """Add a custom loader for an extension.

        Args:
            extension: File extension (e.g., '.pdf')
            loader: DocumentLoader instance
        """
        self.loaders[extension.lower()] = loader

    async def load(self, directory: str | Path) -> list[Document]:
        """Load all documents from directory.

        Args:
            directory: Directory path

        Returns:
            List of all loaded documents
        """
        dir_path = Path(directory)
        if not dir_path.is_dir():
            raise NotADirectoryError(f"Not a directory: {dir_path}")

        if self.recursive:
            files = list(dir_path.glob(self.glob_pattern))
        else:
            files = list(dir_path.glob(self.glob_pattern.replace("**/", "")))

        files = [f for f in files if f.is_file()]

        logger.info(f"Found {len(files)} files to load")

        documents = []
        tasks = []

        for file_path in files:
            extension = file_path.suffix.lower()
            if extension in self.loaders:
                loader = self.loaders[extension]
                tasks.append(self._load_file(loader, file_path))
            else:
                logger.debug(f"No loader for {extension}: {file_path}")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Exception):
                logger.warning(f"Error loading file: {result}")
            elif result:
                documents.extend(result)

        logger.info(f"Loaded {len(documents)} documents")
        return documents

    async def _load_file(self, loader: DocumentLoader, path: Path) -> list[Document]:
        """Load a single file asynchronously.

        Args:
            loader: DocumentLoader instance
            path: File path

        Returns:
            List of loaded documents
        """
        try:
            return await loader.load(path)
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
            return []

    def load_sync(self, directory: str | Path) -> list[Document]:
        """Synchronously load all documents from directory.

        Args:
            directory: Directory path

        Returns:
            List of all loaded documents
        """
        return asyncio.run(self.load(directory))


class TextLoader(DocumentLoader):
    """Load text files."""

    async def load(self, source: str | Path) -> list[Document]:
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
        return [".txt", ".py", ".js", ".ts", ".java", ".go", ".rs", ".yaml", ".yml"]

    def can_load(self, source: str | Path) -> bool:
        """Check if this loader can load the given source."""
        path = Path(source)
        return path.suffix.lower() in self.supported_extensions()
