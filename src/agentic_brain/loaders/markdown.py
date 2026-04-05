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

"""Markdown document loader."""

import logging
import re
from pathlib import Path

from .base import Document, SyncDocumentLoader

logger = logging.getLogger(__name__)


class MarkdownLoader(SyncDocumentLoader):
    """Load Markdown files."""

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load Markdown file."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")

            metadata = {"filename": path.name, "size": path.stat().st_size}

            title_match = re.search(r"^#\s+(.+?)$", content, re.MULTILINE)
            if title_match:
                metadata["title"] = title_match.group(1)

            code_blocks = re.findall(r"```[\w]*\n(.+?)\n```", content, re.DOTALL)
            if code_blocks:
                metadata["code_block_count"] = len(code_blocks)

            links = re.findall(r"\[([^\]]+)\]\(([^\)]+)\)", content)
            if links:
                metadata["links"] = links

            return [
                Document(
                    content=content,
                    source=str(path),
                    metadata=metadata,
                )
            ]

        except Exception as e:
            logger.error(f"Error loading Markdown {path}: {e}")
            raise ValueError(f"Failed to load Markdown: {e}") from e

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".md", ".markdown"]


class MarkdownHeadingLoader(SyncDocumentLoader):
    """Load Markdown files, creating separate documents per heading."""

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load Markdown file, splitting by headings."""
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Markdown file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")

            documents = []
            sections = re.split(r"^(#{1,6}\s+.+?)$", content, flags=re.MULTILINE)

            for i in range(1, len(sections), 2):
                heading = sections[i].strip()
                section_content = (
                    sections[i + 1].strip() if i + 1 < len(sections) else ""
                )

                if section_content:
                    level = len(re.match(r"^#+", heading).group(0))
                    title = heading.lstrip("#").strip()

                    documents.append(
                        Document(
                            content=section_content,
                            source=str(path),
                            metadata={
                                "filename": path.name,
                                "heading": title,
                                "heading_level": level,
                                "size": path.stat().st_size,
                            },
                        )
                    )

            if not documents:
                documents = [
                    Document(
                        content=content,
                        source=str(path),
                        metadata={"filename": path.name, "size": path.stat().st_size},
                    )
                ]

            return documents

        except Exception as e:
            logger.error(f"Error loading Markdown {path}: {e}")
            raise ValueError(f"Failed to load Markdown: {e}") from e

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".md", ".markdown"]
