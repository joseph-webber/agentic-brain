# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

"""API loaders for RAG pipelines.

Supports:
- Generic REST API endpoints
- Paginated APIs
- OAuth2 authentication
"""

import json
import logging
from typing import Any, Callable, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)

# Check for requests
try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class APILoader(BaseLoader):
    """Base loader for REST APIs.

    A flexible loader that can work with any REST API endpoint.

    Example:
        loader = APILoader(
            base_url="https://api.example.com/v1",
            headers={"Authorization": "Bearer token"}
        )
        docs = loader.load_endpoint("/articles")
    """

    def __init__(
        self,
        base_url: str,
        headers: Optional[dict[str, str]] = None,
        auth: Optional[tuple[str, str]] = None,
        timeout: int = 30,
        content_extractor: Optional[Callable[[dict], str]] = None,
        id_field: str = "id",
    ):
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests not installed. Run: pip install requests")

        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.auth = auth
        self.timeout = timeout
        self.content_extractor = content_extractor or self._default_extractor
        self.id_field = id_field
        self._session = None

    @property
    def source_name(self) -> str:
        return "api"

    def authenticate(self) -> bool:
        """Initialize API session."""
        self._session = requests.Session()
        self._session.headers.update(self.headers)
        if self.auth:
            self._session.auth = self.auth
        return True

    def _ensure_authenticated(self):
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to initialize API session")

    def _default_extractor(self, item: dict) -> str:
        """Default content extraction - JSON dump."""
        return json.dumps(item, indent=2, default=str)

    def _get(self, endpoint: str, params: Optional[dict] = None) -> Any:
        """Make GET request to API."""
        url = f"{self.base_url}{endpoint}"
        response = self._session.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single item from the API."""
        self._ensure_authenticated()

        try:
            data = self._get(f"/{doc_id}")
            content = self.content_extractor(data)

            return LoadedDocument(
                content=content,
                source=self.source_name,
                source_id=doc_id,
                filename=f"{doc_id}.json",
                mime_type="application/json",
                metadata=data if isinstance(data, dict) else {"data": data},
            )
        except Exception as e:
            logger.error(f"Failed to load API document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all items from an endpoint."""
        return self.load_endpoint(folder_path)

    def load_endpoint(
        self,
        endpoint: str,
        params: Optional[dict] = None,
        items_key: Optional[str] = None,
    ) -> list[LoadedDocument]:
        """Load items from an API endpoint.

        Args:
            endpoint: API endpoint path
            params: Query parameters
            items_key: Key containing array of items in response
        """
        self._ensure_authenticated()
        docs = []

        try:
            data = self._get(endpoint, params)

            # Find items array
            if items_key:
                items = data.get(items_key, [])
            elif isinstance(data, list):
                items = data
            else:
                items = data.get("data", data.get("results", data.get("items", [data])))

            if not isinstance(items, list):
                items = [items]

            for item in items:
                item_id = item.get(self.id_field, str(hash(str(item))))
                content = self.content_extractor(item)

                docs.append(
                    LoadedDocument(
                        content=content,
                        source=self.source_name,
                        source_id=str(item_id),
                        filename=f"{item_id}.json",
                        mime_type="application/json",
                        metadata=item if isinstance(item, dict) else {},
                    )
                )

        except Exception as e:
            logger.error(f"Failed to load API endpoint {endpoint}: {e}")

        return docs

    def load_paginated(
        self,
        endpoint: str,
        page_param: str = "page",
        limit_param: str = "limit",
        limit: int = 100,
        max_pages: int = 10,
        items_key: Optional[str] = None,
    ) -> list[LoadedDocument]:
        """Load paginated API endpoint."""
        self._ensure_authenticated()
        all_docs = []

        for page in range(1, max_pages + 1):
            params = {page_param: page, limit_param: limit}
            docs = self.load_endpoint(endpoint, params=params, items_key=items_key)

            if not docs:
                break

            all_docs.extend(docs)

            if len(docs) < limit:
                break

        return all_docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search API - override in subclass."""
        logger.warning("Search not implemented for generic API loader")
        return []


class RESTLoader(APILoader):
    """REST API loader with common patterns.

    Extends APILoader with RESTful conventions.
    """

    def __init__(
        self,
        base_url: str,
        resource: str,
        headers: Optional[dict[str, str]] = None,
        auth: Optional[tuple[str, str]] = None,
        **kwargs,
    ):
        super().__init__(base_url, headers, auth, **kwargs)
        self.resource = resource.strip("/")

    def list_all(self, params: Optional[dict] = None) -> list[LoadedDocument]:
        """List all resources."""
        return self.load_endpoint(f"/{self.resource}", params)

    def get_one(self, resource_id: str) -> Optional[LoadedDocument]:
        """Get a single resource by ID."""
        return self.load_document(f"{self.resource}/{resource_id}")


__all__ = ["APILoader", "RESTLoader"]
