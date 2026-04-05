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

"""Text and Markdown file loaders."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..exceptions import LoaderError
from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class TextLoader(BaseLoader):
    """Load plain text files from the local filesystem.

    Example:
        loader = TextLoader(base_path="/documents")
        docs = loader.load_folder("reports/")
        doc = loader.load_document("/documents/readme.txt")
    """

    SUPPORTED_EXTENSIONS = {".txt", ".text", ".log"}

    def __init__(
        self,
        base_path: Optional[str] = None,
        encoding: str = "utf-8",
        max_file_size_mb: int = 10,
    ):
        """Initialize TextLoader.

        Args:
            base_path: Base directory for relative paths
            encoding: File encoding (default: utf-8)
            max_file_size_mb: Maximum file size to load
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.encoding = encoding
        self.max_file_size = max_file_size_mb * 1024 * 1024

    @property
    def source_name(self) -> str:
        return "local_text"

    def authenticate(self) -> bool:
        """No authentication needed for local files."""
        return True

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a text file by path."""
        file_path = self._resolve_path(doc_id)

        try:
            if not file_path.exists():
                raise LoaderError(
                    "File not found",
                    context={"path": str(file_path), "loader": self.source_name},
                )

            if not file_path.is_file():
                raise LoaderError(
                    "Not a file",
                    context={"path": str(file_path), "loader": self.source_name},
                )

            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                raise LoaderError(
                    "File too large",
                    context={
                        "path": str(file_path),
                        "size_bytes": file_size,
                        "max_size_bytes": self.max_file_size,
                        "loader": self.source_name,
                    },
                )

            content = file_path.read_text(encoding=self.encoding)
            stat = file_path.stat()
        except LoaderError:
            raise
        except FileNotFoundError as exc:
            logger.exception("File not found while loading text")
            raise LoaderError(
                "File not found",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc
        except PermissionError as exc:
            logger.exception("Permission denied while reading text")
            raise LoaderError(
                "Permission denied",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc
        except UnicodeDecodeError as exc:
            logger.exception("Encoding error while reading text")
            raise LoaderError(
                "Encoding error",
                context={
                    "path": str(file_path),
                    "encoding": self.encoding,
                    "loader": self.source_name,
                },
            ) from exc
        except OSError as exc:
            logger.exception("I/O error while reading text")
            raise LoaderError(
                "I/O error while reading text",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc

        return LoadedDocument(
            content=content,
            source=self.source_name,
            source_id=str(file_path.absolute()),
            filename=file_path.name,
            mime_type="text/plain",
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            size_bytes=file_size,
            metadata={
                "source": str(file_path.absolute()),
                "extension": file_path.suffix,
                "encoding": self.encoding,
            },
        )

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all text files from a folder."""
        folder = self._resolve_path(folder_path)

        if not folder.exists():
            logger.error(f"Folder not found: {folder}")
            return []

        if not folder.is_dir():
            logger.error(f"Not a directory: {folder}")
            return []

        documents = []
        pattern = "**/*" if recursive else "*"

        for file_path in folder.glob(pattern):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ):
                try:
                    doc = self.load_document(str(file_path))
                except LoaderError as exc:
                    logger.error("Failed to load %s: %s", file_path, exc)
                    continue

                if doc:
                    documents.append(doc)

        logger.info(f"Loaded {len(documents)} text files from {folder}")
        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for text files containing the query string."""
        results = []
        query_lower = query.lower()

        for file_path in self.base_path.rglob("*"):
            if len(results) >= max_results:
                break

            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ):
                try:
                    # First check filename
                    if query_lower in file_path.name.lower():
                        try:
                            doc = self.load_document(str(file_path))
                        except LoaderError as exc:
                            logger.debug("Skipping %s: %s", file_path, exc)
                            continue
                        if doc:
                            results.append(doc)
                            continue

                    # Then check content
                    try:
                        content = file_path.read_text(encoding=self.encoding)
                    except (OSError, UnicodeDecodeError) as exc:
                        logger.debug("Failed to read %s for search: %s", file_path, exc)
                        continue

                    if query_lower in content.lower():
                        try:
                            doc = self.load_document(str(file_path))
                        except LoaderError as exc:
                            logger.debug("Skipping %s: %s", file_path, exc)
                            continue
                        if doc:
                            results.append(doc)
                except Exception:
                    continue

        return results


class MarkdownLoader(BaseLoader):
    """Load Markdown files from the local filesystem.

    Example:
        loader = MarkdownLoader(base_path="/docs")
        docs = loader.load_folder("guides/")
    """

    SUPPORTED_EXTENSIONS = {".md", ".markdown", ".mdown", ".mkd"}

    def __init__(
        self,
        base_path: Optional[str] = None,
        encoding: str = "utf-8",
        max_file_size_mb: int = 10,
        strip_frontmatter: bool = True,
    ):
        """Initialize MarkdownLoader.

        Args:
            base_path: Base directory for relative paths
            encoding: File encoding (default: utf-8)
            max_file_size_mb: Maximum file size to load
            strip_frontmatter: Remove YAML frontmatter from content
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.encoding = encoding
        self.max_file_size = max_file_size_mb * 1024 * 1024
        self.strip_frontmatter = strip_frontmatter

    @property
    def source_name(self) -> str:
        return "local_markdown"

    def authenticate(self) -> bool:
        """No authentication needed for local files."""
        return True

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p

    def _parse_frontmatter(self, content: str) -> tuple[str, dict]:
        """Parse YAML frontmatter if present.

        Returns:
            Tuple of (content_without_frontmatter, frontmatter_dict)
        """
        import re

        frontmatter = {}

        # Check for YAML frontmatter (--- at start)
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if match:
            try:
                import yaml

                frontmatter = yaml.safe_load(match.group(1)) or {}
            except ImportError:
                # Parse simple key: value pairs
                for line in match.group(1).split("\n"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        frontmatter[key.strip()] = value.strip()
            except Exception:
                pass

            if self.strip_frontmatter:
                content = content[match.end() :]

        return content, frontmatter

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a markdown file by path."""
        file_path = self._resolve_path(doc_id)

        try:
            if not file_path.exists():
                raise LoaderError(
                    "File not found",
                    context={"path": str(file_path), "loader": self.source_name},
                )

            if not file_path.is_file():
                raise LoaderError(
                    "Not a file",
                    context={"path": str(file_path), "loader": self.source_name},
                )

            file_size = file_path.stat().st_size
            if file_size > self.max_file_size:
                raise LoaderError(
                    "File too large",
                    context={
                        "path": str(file_path),
                        "size_bytes": file_size,
                        "max_size_bytes": self.max_file_size,
                        "loader": self.source_name,
                    },
                )

            raw_content = file_path.read_text(encoding=self.encoding)
            content, frontmatter = self._parse_frontmatter(raw_content)
            stat = file_path.stat()
        except LoaderError:
            raise
        except FileNotFoundError as exc:
            logger.exception("File not found while loading markdown")
            raise LoaderError(
                "File not found",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc
        except PermissionError as exc:
            logger.exception("Permission denied while reading markdown")
            raise LoaderError(
                "Permission denied",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc
        except UnicodeDecodeError as exc:
            logger.exception("Encoding error while reading markdown")
            raise LoaderError(
                "Encoding error",
                context={
                    "path": str(file_path),
                    "encoding": self.encoding,
                    "loader": self.source_name,
                },
            ) from exc
        except OSError as exc:
            logger.exception("I/O error while reading markdown")
            raise LoaderError(
                "I/O error while reading markdown",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc

        metadata = {
            "source": str(file_path.absolute()),
            "extension": file_path.suffix,
            "encoding": self.encoding,
        }
        if frontmatter:
            metadata["frontmatter"] = frontmatter

        return LoadedDocument(
            content=content,
            source=self.source_name,
            source_id=str(file_path.absolute()),
            filename=file_path.name,
            mime_type="text/markdown",
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            size_bytes=file_size,
            metadata=metadata,
        )

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all markdown files from a folder."""
        folder = self._resolve_path(folder_path)

        if not folder.exists():
            logger.error(f"Folder not found: {folder}")
            return []

        if not folder.is_dir():
            logger.error(f"Not a directory: {folder}")
            return []

        documents = []
        pattern = "**/*" if recursive else "*"

        for file_path in folder.glob(pattern):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ):
                try:
                    doc = self.load_document(str(file_path))
                except LoaderError as exc:
                    logger.error("Failed to load %s: %s", file_path, exc)
                    continue

                if doc:
                    documents.append(doc)

        logger.info(f"Loaded {len(documents)} markdown files from {folder}")
        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for markdown files containing the query string."""
        results = []
        query_lower = query.lower()

        for file_path in self.base_path.rglob("*"):
            if len(results) >= max_results:
                break

            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
            ):
                try:
                    if query_lower in file_path.name.lower():
                        try:
                            doc = self.load_document(str(file_path))
                        except LoaderError as exc:
                            logger.debug("Skipping %s: %s", file_path, exc)
                            continue
                        if doc:
                            results.append(doc)
                            continue

                    try:
                        content = file_path.read_text(encoding=self.encoding)
                    except (OSError, UnicodeDecodeError) as exc:
                        logger.debug("Failed to read %s for search: %s", file_path, exc)
                        continue

                    if query_lower in content.lower():
                        try:
                            doc = self.load_document(str(file_path))
                        except LoaderError as exc:
                            logger.debug("Skipping %s: %s", file_path, exc)
                            continue
                        if doc:
                            results.append(doc)
                except Exception:
                    continue

        return results


__all__ = ["TextLoader", "MarkdownLoader"]
