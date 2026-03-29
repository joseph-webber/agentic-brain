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

"""Confluence loader for RAG pipelines."""

import logging
from typing import Any, Dict, List, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for atlassian-python-api
try:
    from atlassian import Confluence

    CONFLUENCE_AVAILABLE = True
except ImportError:
    CONFLUENCE_AVAILABLE = False


class ConfluenceLoader(BaseLoader):
    """Load pages from Atlassian Confluence.

    Supports:
    - Pages by space
    - Pages by CQL query
    - Page content and attachments
    - Comments and metadata

    Example:
        loader = ConfluenceLoader(
            url="https://company.atlassian.net/wiki",
            username="user@company.com",
            token="api-token"
        )
        docs = loader.load_space("ENGINEERING")
    """

    def __init__(
        self,
        url: str,
        username: Optional[str] = None,
        token: Optional[str] = None,
        api_key: Optional[str] = None,
        cloud: bool = True,
    ):
        """Initialize Confluence loader.

        Args:
            url: Confluence base URL
            username: Username (email for cloud)
            token: API token or password
            api_key: Alternative API key auth
            cloud: Whether using Atlassian Cloud (default True)
        """
        super().__init__()
        self._url = url
        self._username = username
        self._token = token
        self._api_key = api_key
        self._cloud = cloud
        self._client = None

    @property
    def source_name(self) -> str:
        """Return source name."""
        return "confluence"

    def authenticate(self) -> bool:
        """Authenticate with Confluence API."""
        if not CONFLUENCE_AVAILABLE:
            raise ImportError(
                "atlassian-python-api not installed. "
                "Run: pip install atlassian-python-api"
            )

        try:
            self._client = Confluence(
                url=self._url,
                username=self._username,
                password=self._token,
                cloud=self._cloud,
            )
            # Test connection
            self._client.get_all_spaces(limit=1)
            self._authenticated = True
            return True

        except Exception as e:
            logger.error(f"Confluence authentication failed: {e}")
            self._authenticated = False
            return False

    def load_page(self, page_id: str) -> LoadedDocument:
        """Load a single page by ID."""
        if not self._authenticated:
            self.authenticate()

        page = self._client.get_page_by_id(page_id, expand="body.storage,version,space")

        content = page.get("body", {}).get("storage", {}).get("value", "")
        # Strip HTML tags for plain text
        import re

        plain_text = re.sub(r"<[^>]+>", " ", content)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()

        return LoadedDocument(
            content=plain_text,
            source=f"confluence://{page_id}",
            title=page.get("title", page_id),
            metadata={
                "page_id": page_id,
                "space_key": page.get("space", {}).get("key"),
                "version": page.get("version", {}).get("number"),
                "last_modified": page.get("version", {}).get("when"),
            },
        )

    def load_folder(self, folder_path: str) -> List[LoadedDocument]:
        """Load all pages from a space (folder_path = space key)."""
        return self.load_space(folder_path)

    def load_space(
        self, space_key: str, include_archived: bool = False
    ) -> List[LoadedDocument]:
        """Load all pages from a Confluence space."""
        if not self._authenticated:
            self.authenticate()

        documents = []
        start = 0
        limit = 50

        while True:
            pages = self._client.get_all_pages_from_space(
                space_key, start=start, limit=limit, content_type="page"
            )

            if not pages:
                break

            for page in pages:
                try:
                    doc = self.load_page(page["id"])
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"Failed to load page {page.get('title')}: {e}")

            if len(pages) < limit:
                break
            start += limit

        return documents

    def search(self, cql: str, max_results: int = 100) -> List[LoadedDocument]:
        """Search using Confluence Query Language (CQL)."""
        if not self._authenticated:
            self.authenticate()

        documents = []
        results = self._client.cql(cql, limit=max_results)

        for result in results.get("results", []):
            if result.get("content", {}).get("type") == "page":
                try:
                    doc = self.load_page(result["content"]["id"])
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"Failed to load search result: {e}")

        return documents
