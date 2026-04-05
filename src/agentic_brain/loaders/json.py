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

"""JSON file loader."""

import json
import logging
from pathlib import Path

from .base import Document, SyncDocumentLoader

logger = logging.getLogger(__name__)


class JSONLoader(SyncDocumentLoader):
    """Load JSON files."""

    def __init__(self, encoding: str = "utf-8", jq_filter: str | None = None):
        """Initialize JSON loader.

        Args:
            encoding: File encoding (default: utf-8)
            jq_filter: Optional jq-like filter path (e.g., 'data.items')
        """
        self.encoding = encoding
        self.jq_filter = jq_filter

    def _extract_by_path(self, data: dict, path: str):
        """Extract data using dot notation path."""
        keys = path.split(".")
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            elif isinstance(current, list):
                try:
                    current = current[int(key)]
                except (ValueError, IndexError):
                    return None
            else:
                return None
        return current

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load JSON file."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"JSON file not found: {path}")

        try:
            content_str = path.read_text(encoding=self.encoding)
            data = json.loads(content_str)

            if self.jq_filter:
                data = self._extract_by_path(data, self.jq_filter)

            content = json.dumps(data, indent=2)

            return [
                Document(
                    content=content,
                    source=str(path),
                    metadata={
                        "filename": path.name,
                        "size": path.stat().st_size,
                        "encoding": self.encoding,
                        "jq_filter": self.jq_filter,
                    },
                )
            ]

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {path}: {e}")
            raise ValueError(f"Invalid JSON file: {e}") from e
        except Exception as e:
            logger.error(f"Error loading JSON {path}: {e}")
            raise ValueError(f"Failed to load JSON: {e}") from e

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".json"]


class JSONLinesLoader(SyncDocumentLoader):
    """Load JSONL (JSON Lines) files."""

    def __init__(self, encoding: str = "utf-8"):
        """Initialize JSONL loader.

        Args:
            encoding: File encoding (default: utf-8)
        """
        self.encoding = encoding

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load JSONL file as single document."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"JSONL file not found: {path}")

        try:
            lines = path.read_text(encoding=self.encoding).strip().split("\n")
            entries = []

            for line in lines:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping invalid JSON line: {e}")

            content = json.dumps(entries, indent=2)

            return [
                Document(
                    content=content,
                    source=str(path),
                    metadata={
                        "filename": path.name,
                        "line_count": len(entries),
                        "size": path.stat().st_size,
                        "encoding": self.encoding,
                    },
                )
            ]

        except Exception as e:
            logger.error(f"Error loading JSONL {path}: {e}")
            raise ValueError(f"Failed to load JSONL: {e}") from e

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".jsonl", ".ndjson"]


class JSONLinesRowLoader(SyncDocumentLoader):
    """Load JSONL files, creating separate document per line."""

    def __init__(self, encoding: str = "utf-8"):
        """Initialize JSONL row loader.

        Args:
            encoding: File encoding (default: utf-8)
        """
        self.encoding = encoding

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load JSONL file, one document per line."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"JSONL file not found: {path}")

        documents = []
        try:
            lines = path.read_text(encoding=self.encoding).strip().split("\n")

            for line_num, line in enumerate(lines, 1):
                if line.strip():
                    try:
                        entry = json.loads(line)
                        content = json.dumps(entry, indent=2)

                        documents.append(
                            Document(
                                content=content,
                                source=str(path),
                                metadata={
                                    "filename": path.name,
                                    "line_number": line_num,
                                    "size": path.stat().st_size,
                                    "encoding": self.encoding,
                                },
                            )
                        )
                    except json.JSONDecodeError as e:
                        logger.warning(f"Skipping invalid JSON line {line_num}: {e}")

        except Exception as e:
            logger.error(f"Error loading JSONL {path}: {e}")
            raise ValueError(f"Failed to load JSONL: {e}") from e

        return documents

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".jsonl", ".ndjson"]
