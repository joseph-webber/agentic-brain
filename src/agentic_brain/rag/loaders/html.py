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

"""HTML and web page loaders for RAG pipelines."""

import logging
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for requests
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# Check for BeautifulSoup
try:
    from bs4 import BeautifulSoup

    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


class HTMLLoader(BaseLoader):
    """Load and extract text from HTML files.

    Example:
        loader = HTMLLoader()
        doc = loader.load_document("page.html")
        docs = loader.load_folder("html_pages/")
    """

    def __init__(
        self,
        base_path: str = ".",
        include_links: bool = False,
        include_images: bool = False,
    ):
        self.base_path = Path(base_path)
        self.include_links = include_links
        self.include_images = include_images

    @property
    def source_name(self) -> str:
        return "html"

    def authenticate(self) -> bool:
        return True

    def _clean_html(self, html: str) -> str:
        """Extract text from HTML."""
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, "html.parser")

            # Remove unwanted elements
            for element in soup(
                ["script", "style", "head", "meta", "link", "nav", "footer"]
            ):
                element.decompose()

            # Get text
            text = soup.get_text(separator="\n")

            # Clean whitespace
            lines = (line.strip() for line in text.splitlines())
            return "\n".join(line for line in lines if line)
        else:
            # Basic regex fallback
            text = re.sub(
                r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
            )
            text = re.sub(
                r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE
            )
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            return text.strip()

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single HTML file."""
        try:
            path = Path(doc_id)
            if not path.is_absolute():
                path = self.base_path / path

            if not path.exists():
                logger.error(f"File not found: {path}")
                return None

            with open(path, encoding="utf-8", errors="replace") as f:
                html = f.read()

            content = self._clean_html(html)

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=str(path),
                filename=path.name,
                mime_type="text/html",
                size_bytes=len(html.encode()),
                metadata={"path": str(path)},
            )
        except Exception as e:
            logger.error(f"Failed to load HTML {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all HTML files from a folder."""
        docs = []
        path = Path(folder_path)
        if not path.is_absolute():
            path = self.base_path / path

        if not path.exists():
            return docs

        patterns = ["**/*.html", "**/*.htm"] if recursive else ["*.html", "*.htm"]

        for pattern in patterns:
            for html_path in path.glob(pattern):
                doc = self.load_document(str(html_path))
                if doc:
                    docs.append(doc)

        logger.info(f"Loaded {len(docs)} HTML files from {folder_path}")
        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search not supported for local files."""
        return []


class WebLoader(BaseLoader):
    """Load and extract content from web URLs.

    Example:
        loader = WebLoader()
        doc = loader.load_document("https://example.com/page")
        docs = loader.crawl("https://example.com", max_pages=10)
    """

    def __init__(
        self,
        user_agent: str = "Mozilla/5.0 (compatible; AgenticBrainBot/1.0)",
        timeout: int = 30,
        follow_redirects: bool = True,
    ):
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests not installed. Run: pip install requests")

        self.user_agent = user_agent
        self.timeout = timeout
        self.follow_redirects = follow_redirects
        self._session = None

    @property
    def source_name(self) -> str:
        return "web"

    def authenticate(self) -> bool:
        self._session = requests.Session()
        self._session.headers["User-Agent"] = self.user_agent
        return True

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to initialize web session")

    def _clean_html(self, html: str) -> str:
        """Extract text from HTML."""
        if BS4_AVAILABLE:
            soup = BeautifulSoup(html, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "aside"]):
                element.decompose()
            text = soup.get_text(separator="\n")
            lines = (line.strip() for line in text.splitlines())
            return "\n".join(line for line in lines if line)
        else:
            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            return re.sub(r"\s+", " ", text).strip()

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load content from a URL."""
        self._ensure_authenticated()

        try:
            response = self._session.get(
                doc_id,
                timeout=self.timeout,
                allow_redirects=self.follow_redirects,
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "html" in content_type:
                content = self._clean_html(response.text)
            else:
                content = response.text

            parsed = urlparse(doc_id)

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=parsed.path.split("/")[-1] or "index",
                mime_type=content_type.split(";")[0],
                size_bytes=len(response.content),
                metadata={
                    "url": doc_id,
                    "domain": parsed.netloc,
                    "status_code": response.status_code,
                },
            )
        except Exception as e:
            logger.error(f"Failed to load URL {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Not applicable for web - use crawl() instead."""
        logger.warning("Use crawl() for web pages")
        return []

    def crawl(
        self,
        start_url: str,
        max_pages: int = 10,
        same_domain_only: bool = True,
    ) -> list[LoadedDocument]:
        """Crawl a website starting from a URL."""
        self._ensure_authenticated()

        if not BS4_AVAILABLE:
            logger.error("BeautifulSoup required for crawling")
            return []

        docs = []
        visited = set()
        to_visit = [start_url]
        base_domain = urlparse(start_url).netloc

        while to_visit and len(docs) < max_pages:
            url = to_visit.pop(0)
            if url in visited:
                continue

            visited.add(url)
            doc = self.load_document(url)
            if not doc:
                continue

            docs.append(doc)

            # Extract links
            try:
                response = self._session.get(url, timeout=self.timeout)
                soup = BeautifulSoup(response.text, "html.parser")

                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    full_url = urljoin(url, href)
                    parsed = urlparse(full_url)

                    if same_domain_only and parsed.netloc != base_domain:
                        continue

                    if full_url not in visited and full_url not in to_visit:
                        to_visit.append(full_url)
            except Exception:
                pass

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Web search not implemented - use a search API."""
        return []


__all__ = ["HTMLLoader", "WebLoader"]
