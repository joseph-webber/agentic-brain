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

"""JSON and JSONL file loaders."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..exceptions import LoaderError
from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


class JSONLoader(BaseLoader):
    """Load JSON files from the local filesystem.

    Can extract text content from specific fields or format the entire JSON.

    Example:
        # Load entire JSON as text
        loader = JSONLoader(base_path="/data")
        docs = loader.load_folder("configs/")

        # Extract specific field
        loader = JSONLoader(content_key="body")
        doc = loader.load_document("article.json")
    """

    SUPPORTED_EXTENSIONS = {".json"}

    def __init__(
        self,
        base_path: Optional[str] = None,
        encoding: str = "utf-8",
        content_key: Optional[str] = None,
        jq_filter: Optional[str] = None,
        max_file_size_mb: int = 50,
    ):
        """Initialize JSONLoader.

        Args:
            base_path: Base directory for relative paths
            encoding: File encoding (default: utf-8)
            content_key: Extract content from this key (dot notation: "data.content")
            jq_filter: JQ-style filter for content extraction
            max_file_size_mb: Maximum file size to load
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.encoding = encoding
        self.content_key = content_key
        self.jq_filter = jq_filter
        self.max_file_size = max_file_size_mb * 1024 * 1024

    @property
    def source_name(self) -> str:
        return "local_json"

    def authenticate(self) -> bool:
        """No authentication needed for local files."""
        return True

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p

    def _extract_by_key(self, data: Any, key: str) -> Any:
        """Extract value using dot notation (e.g., 'data.content.text')."""
        parts = key.split(".")
        result = data
        for part in parts:
            if isinstance(result, dict):
                result = result.get(part)
            elif isinstance(result, list) and part.isdigit():
                idx = int(part)
                result = result[idx] if idx < len(result) else None
            else:
                return None
            if result is None:
                return None
        return result

    def _format_content(self, data: Any) -> str:
        """Format JSON data as readable text."""
        if self.content_key:
            extracted = self._extract_by_key(data, self.content_key)
            if extracted is not None:
                if isinstance(extracted, str):
                    return extracted
                return json.dumps(extracted, indent=2, ensure_ascii=False)

        # Default: format entire JSON
        if isinstance(data, str):
            return data
        return json.dumps(data, indent=2, ensure_ascii=False)

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a JSON file by path."""
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
            data = json.loads(raw_content)
            content = self._format_content(data)
            stat = file_path.stat()
        except LoaderError:
            raise
        except FileNotFoundError as exc:
            logger.exception("File not found while loading JSON")
            raise LoaderError(
                "File not found",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc
        except PermissionError as exc:
            logger.exception("Permission denied while reading JSON")
            raise LoaderError(
                "Permission denied",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc
        except UnicodeDecodeError as exc:
            logger.exception("Encoding error while reading JSON")
            raise LoaderError(
                "Encoding error",
                context={"path": str(file_path), "encoding": self.encoding, "loader": self.source_name},
            ) from exc
        except json.JSONDecodeError as exc:
            logger.exception("Invalid JSON file")
            raise LoaderError(
                "Corrupt JSON file",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc
        except OSError as exc:
            logger.exception("I/O error while reading JSON")
            raise LoaderError(
                "I/O error while reading JSON",
                context={"path": str(file_path), "loader": self.source_name},
            ) from exc

        metadata = {
            "extension": file_path.suffix,
            "encoding": self.encoding,
            "json_type": type(data).__name__,
        }
        if self.content_key:
            metadata["content_key"] = self.content_key

        return LoadedDocument(
            content=content,
            source=self.source_name,
            source_id=str(file_path.absolute()),
            filename=file_path.name,
            mime_type="application/json",
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            size_bytes=file_size,
            metadata=metadata,
        )

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all JSON files from a folder."""
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

        logger.info(f"Loaded {len(documents)} JSON files from {folder}")
        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for JSON files containing the query string."""
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


class JSONLLoader(BaseLoader):
    """Load JSON Lines (JSONL) files - one JSON object per line.

    Example:
        loader = JSONLLoader(base_path="/logs", content_key="message")
        docs = loader.load_folder("events/")
    """

    SUPPORTED_EXTENSIONS = {".jsonl", ".ndjson"}

    def __init__(
        self,
        base_path: Optional[str] = None,
        encoding: str = "utf-8",
        content_key: Optional[str] = None,
        one_doc_per_line: bool = False,
        max_file_size_mb: int = 100,
    ):
        """Initialize JSONLLoader.

        Args:
            base_path: Base directory for relative paths
            encoding: File encoding (default: utf-8)
            content_key: Extract content from this key in each line
            one_doc_per_line: Create separate LoadedDocument per line
            max_file_size_mb: Maximum file size to load
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.encoding = encoding
        self.content_key = content_key
        self.one_doc_per_line = one_doc_per_line
        self.max_file_size = max_file_size_mb * 1024 * 1024

    @property
    def source_name(self) -> str:
        return "local_jsonl"

    def authenticate(self) -> bool:
        """No authentication needed for local files."""
        return True

    def _resolve_path(self, path: str) -> Path:
        """Resolve path relative to base_path."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.base_path / p

    def _extract_by_key(self, data: dict, key: str) -> Any:
        """Extract value using dot notation."""
        parts = key.split(".")
        result = data
        for part in parts:
            if isinstance(result, dict):
                result = result.get(part)
            else:
                return None
            if result is None:
                return None
        return result

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a JSONL file by path.

        If one_doc_per_line=False, combines all lines into one document.
        """
        file_path = self._resolve_path(doc_id)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        if not file_path.is_file():
            logger.error(f"Not a file: {file_path}")
            return None

        file_size = file_path.stat().st_size
        if file_size > self.max_file_size:
            logger.warning(f"File too large: {file_path} ({file_size} bytes)")
            return None

        try:
            lines = []
            line_count = 0
            with open(file_path, encoding=self.encoding) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    line_count += 1
                    try:
                        data = json.loads(line)
                        if self.content_key:
                            extracted = self._extract_by_key(data, self.content_key)
                            if extracted is not None:
                                lines.append(str(extracted))
                        else:
                            lines.append(json.dumps(data, ensure_ascii=False))
                    except json.JSONDecodeError:
                        logger.debug(f"Skipping invalid JSON line in {file_path}")

            content = "\n".join(lines)
            stat = file_path.stat()

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(file_path.absolute()),
                filename=file_path.name,
                mime_type="application/x-ndjson",
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=file_size,
                metadata={
                    "extension": file_path.suffix,
                    "encoding": self.encoding,
                    "line_count": line_count,
                },
            )
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all JSONL files from a folder."""
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
                doc = self.load_document(str(file_path))
                if doc:
                    documents.append(doc)

        logger.info(f"Loaded {len(documents)} JSONL files from {folder}")
        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for JSONL files containing the query string."""
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
                        doc = self.load_document(str(file_path))
                        if doc:
                            results.append(doc)
                            continue

                    with open(file_path, encoding=self.encoding) as f:
                        for line in f:
                            if query_lower in line.lower():
                                doc = self.load_document(str(file_path))
                                if doc:
                                    results.append(doc)
                                break
                except Exception:
                    continue

        return results


__all__ = ["JSONLoader", "JSONLLoader"]
