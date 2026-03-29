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

"""YAML file loaders for RAG pipelines."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for PyYAML
try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


class YAMLLoader(BaseLoader):
    """Load YAML files from the local filesystem.

    Supports both single-document and multi-document YAML files.

    Example:
        loader = YAMLLoader(base_path="/configs")
        docs = loader.load_folder("settings/")
        doc = loader.load_document("config.yaml")

        # Extract specific key
        loader = YAMLLoader(content_key="database.connection")
        doc = loader.load_document("app.yml")
    """

    SUPPORTED_EXTENSIONS = {".yaml", ".yml"}

    def __init__(
        self,
        base_path: Optional[str] = None,
        encoding: str = "utf-8",
        content_key: Optional[str] = None,
        multi_document: bool = False,
        max_file_size_mb: int = 50,
    ):
        """Initialize YAMLLoader.

        Args:
            base_path: Base directory for relative paths
            encoding: File encoding (default: utf-8)
            content_key: Extract content from this key (dot notation: "app.config")
            multi_document: Handle multi-document YAML files (--- separators)
            max_file_size_mb: Maximum file size to load
        """
        if not YAML_AVAILABLE:
            raise ImportError("PyYAML not installed. Run: pip install pyyaml")

        self.base_path = Path(base_path) if base_path else Path.cwd()
        self.encoding = encoding
        self.content_key = content_key
        self.multi_document = multi_document
        self.max_file_size = max_file_size_mb * 1024 * 1024

    @property
    def source_name(self) -> str:
        return "local_yaml"

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
        """Extract value using dot notation (e.g., 'database.host')."""
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
        """Format YAML data as readable text."""
        if self.content_key:
            extracted = self._extract_by_key(data, self.content_key)
            if extracted is not None:
                if isinstance(extracted, str):
                    return extracted
                return yaml.dump(extracted, default_flow_style=False, allow_unicode=True)

        # Default: format entire YAML
        if isinstance(data, str):
            return data
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a YAML file by path."""
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
            raw_content = file_path.read_text(encoding=self.encoding)

            if self.multi_document:
                # Parse all documents in the file
                documents = list(yaml.safe_load_all(raw_content))
                if len(documents) == 1:
                    data = documents[0]
                else:
                    data = documents
            else:
                data = yaml.safe_load(raw_content)

            content = self._format_content(data)
            stat = file_path.stat()

            metadata = {
                "extension": file_path.suffix,
                "encoding": self.encoding,
                "yaml_type": type(data).__name__,
            }
            if self.content_key:
                metadata["content_key"] = self.content_key
            if self.multi_document and isinstance(data, list):
                metadata["document_count"] = len(data)

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(file_path.absolute()),
                filename=file_path.name,
                mime_type="application/x-yaml",
                created_at=datetime.fromtimestamp(stat.st_ctime),
                modified_at=datetime.fromtimestamp(stat.st_mtime),
                size_bytes=file_size,
                metadata=metadata,
            )
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading {file_path}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all YAML files from a folder."""
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

        logger.info(f"Loaded {len(documents)} YAML files from {folder}")
        return documents

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search for YAML files containing the query string."""
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
                        doc = self.load_document(str(file_path))
                        if doc:
                            results.append(doc)
                            continue

                    # Then check content
                    content = file_path.read_text(encoding=self.encoding)
                    if query_lower in content.lower():
                        doc = self.load_document(str(file_path))
                        if doc:
                            results.append(doc)
                except Exception:
                    continue

        return results


__all__ = ["YAMLLoader", "YAML_AVAILABLE"]
