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

"""CSV file loader."""

import csv
import logging
from pathlib import Path
from typing import Optional

from .base import Document, SyncDocumentLoader

logger = logging.getLogger(__name__)


class CSVLoader(SyncDocumentLoader):
    """Load CSV files as single document."""

    def __init__(self, encoding: str = "utf-8"):
        """Initialize CSV loader.

        Args:
            encoding: File encoding (default: utf-8)
        """
        self.encoding = encoding

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load CSV file as single document."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        try:
            with open(path, "r", encoding=self.encoding) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            text_lines = []
            if rows:
                headers = list(rows[0].keys())
                text_lines.append(" | ".join(headers))
                text_lines.append(
                    "-" * (sum(len(h) for h in headers) + 3 * len(headers))
                )

                for row in rows:
                    values = [str(row.get(h, "")) for h in headers]
                    text_lines.append(" | ".join(values))

            content = "\n".join(text_lines)

            return [
                Document(
                    content=content,
                    source=str(path),
                    metadata={
                        "filename": path.name,
                        "row_count": len(rows),
                        "column_count": len(rows[0]) if rows else 0,
                        "size": path.stat().st_size,
                        "encoding": self.encoding,
                    },
                )
            ]

        except Exception as e:
            logger.error(f"Error loading CSV {path}: {e}")
            raise ValueError(f"Failed to load CSV: {e}") from e

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".csv"]


class CSVRowLoader(SyncDocumentLoader):
    """Load CSV files, creating separate document per row."""

    def __init__(self, encoding: str = "utf-8"):
        """Initialize CSV row loader.

        Args:
            encoding: File encoding (default: utf-8)
        """
        self.encoding = encoding

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load CSV file, one document per row."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")

        documents = []
        try:
            with open(path, "r", encoding=self.encoding) as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            for row_num, row in enumerate(rows, 1):
                text_parts = []
                for key, value in row.items():
                    text_parts.append(f"{key}: {value}")

                content = "\n".join(text_parts)

                documents.append(
                    Document(
                        content=content,
                        source=str(path),
                        metadata={
                            "filename": path.name,
                            "row_number": row_num,
                            "total_rows": len(rows),
                            "size": path.stat().st_size,
                            "encoding": self.encoding,
                        },
                    )
                )

        except Exception as e:
            logger.error(f"Error loading CSV {path}: {e}")
            raise ValueError(f"Failed to load CSV: {e}") from e

        return documents

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".csv"]
