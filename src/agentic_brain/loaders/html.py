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

"""HTML document loader."""

import logging
from pathlib import Path
from typing import Optional

from .base import Document, SyncDocumentLoader

logger = logging.getLogger(__name__)


class HTMLLoader(SyncDocumentLoader):
    """Load HTML files and extract text content."""

    def __init__(self, extract_links: bool = False, extract_metadata: bool = True):
        """Initialize HTML loader.

        Args:
            extract_links: Whether to include links in output
            extract_metadata: Whether to extract metadata (title, etc)
        """
        self.extract_links = extract_links
        self.extract_metadata = extract_metadata

    def load_sync(self, source: str | Path) -> list[Document]:
        """Load HTML file."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise ImportError(
                "beautifulsoup4 not installed. Install with: pip install beautifulsoup4"
            ) from None

        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"HTML file not found: {path}")

        try:
            content = path.read_text(encoding="utf-8")
            soup = BeautifulSoup(content, "html.parser")

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text(separator="\n", strip=True)

            metadata = {"filename": path.name, "size": path.stat().st_size}

            if self.extract_metadata:
                title = soup.find("title")
                if title:
                    metadata["title"] = title.get_text()

                meta_desc = soup.find("meta", attrs={"name": "description"})
                if meta_desc:
                    metadata["description"] = meta_desc.get("content", "")

            if self.extract_links:
                links = []
                for link in soup.find_all("a", href=True):
                    links.append(link["href"])
                if links:
                    metadata["links"] = links

            return [
                Document(
                    content=text,
                    source=str(path),
                    metadata=metadata,
                )
            ]

        except Exception as e:
            logger.error(f"Error loading HTML {path}: {e}")
            raise ValueError(f"Failed to load HTML: {e}") from e

    def supported_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".html", ".htm"]
