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

"""WordPress RAG loader.

Loads WordPress content (posts, pages, and custom post types) via the WordPress
REST API v2 into :class:`~agentic_brain.rag.loaders.base.LoadedDocument` objects.

Key features:
- Preserves metadata and relationships (taxonomies, author, featured media, _links)
- Gutenberg-aware: strips HTML safely for RAG text ingestion
- ACF support (preserves `acf` fields when exposed via a plugin)
- Incremental sync via `load_since()` using `modified_after` where supported

For richer "headless CMS" workflows (GraphQL/WPGraphQL, block parsing, write
operations), see :class:`agentic_brain.commerce.wordpress_cms.HeadlessCMS`.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime, timezone
from typing import Any, Optional

from .base import BaseLoader, LoadedDocument

logger = logging.getLogger(__name__)


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


class WordPressLoader(BaseLoader):
    """Load WordPress content via REST API v2."""

    def __init__(
        self,
        site_url: Optional[str] = None,
        *,
        username: Optional[str] = None,
        application_password: Optional[str] = None,
        bearer_token: Optional[str] = None,
        api_namespace: str = "wp-json/wp/v2",
        timeout: int = 30,
        default_status: str = "publish",
        include_embed: bool = True,
    ):
        self.site_url = (site_url or os.getenv("WORDPRESS_URL", "")).rstrip("/")
        self.username = username or os.getenv("WORDPRESS_USERNAME")
        self.application_password = application_password or os.getenv(
            "WORDPRESS_APP_PASSWORD"
        )
        self.bearer_token = bearer_token or os.getenv("WORDPRESS_BEARER_TOKEN")
        self.api_namespace = api_namespace.strip("/")
        self.timeout = timeout
        self.default_status = default_status
        self.include_embed = include_embed
        self._session = None

    @property
    def source_name(self) -> str:
        return "wordpress"

    @property
    def base_url(self) -> str:
        if not self.site_url:
            return ""
        return f"{self.site_url}/{self.api_namespace}"

    def authenticate(self) -> bool:
        """Initialize session and validate REST endpoint."""

        try:
            import requests

            if not self.site_url:
                logger.error("WORDPRESS_URL/site_url is required")
                return False

            self._session = requests.Session()
            self._session.headers.update({"Accept": "application/json"})
            if self.bearer_token:
                self._session.headers["Authorization"] = f"Bearer {self.bearer_token}"
            elif self.username and self.application_password:
                self._session.auth = (self.username, self.application_password)

            resp = self._session.get(f"{self.base_url}/types", timeout=self.timeout)
            resp.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"WordPress authentication failed: {e}")
            return False

    def close(self) -> None:
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass

    def _ensure_authenticated(self) -> None:
        if not self._session and not self.authenticate():
            raise RuntimeError("Failed to authenticate with WordPress")

    def _get(self, endpoint: str, *, params: Optional[dict[str, Any]] = None) -> Any:
        self._ensure_authenticated()
        endpoint = endpoint.lstrip("/")
        url = f"{self.base_url}/{endpoint}"
        resp = self._session.get(url, params=params, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def _list_paginated(
        self,
        endpoint: str,
        *,
        params: Optional[dict[str, Any]] = None,
        per_page: int = 100,
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        base_params: dict[str, Any] = dict(params) if params else {}
        base_params.setdefault("per_page", per_page)
        if self.include_embed:
            base_params.setdefault("_embed", "1")

        for page in range(1, max_pages + 1):
            page_params = dict(base_params)
            page_params["page"] = page
            batch = self._get(endpoint, params=page_params)
            if not isinstance(batch, list):
                # Some endpoints might return a single object.
                return [batch]
            if not batch:
                break
            out.extend(batch)
            if len(batch) < per_page:
                break

        return out

    def _extract_text(self, item: dict[str, Any]) -> str:
        title = (item.get("title") or {}).get("rendered") or ""
        excerpt = (item.get("excerpt") or {}).get("rendered") or ""
        content = (item.get("content") or {}).get("rendered") or ""

        title_text = self._clean_html(title)
        excerpt_text = self._clean_html(excerpt)
        content_text = self._clean_html(content)

        parts = [title_text.strip(), excerpt_text.strip(), content_text.strip()]
        return "\n\n".join(p for p in parts if p)

    def _to_loaded_document(
        self, endpoint: str, item: dict[str, Any]
    ) -> LoadedDocument:
        item_id = item.get("id", "")
        slug = item.get("slug") or str(item_id)
        modified = _parse_dt(item.get("modified_gmt") or item.get("modified"))
        created = _parse_dt(item.get("date_gmt") or item.get("date"))

        relationships = {
            "author": item.get("author"),
            "parent": item.get("parent"),
            "featured_media": item.get("featured_media"),
            "categories": item.get("categories"),
            "tags": item.get("tags"),
            "_links": item.get("_links"),
        }

        metadata = {
            "wordpress": {
                "site": self.site_url,
                "endpoint": endpoint,
                "id": item_id,
                "slug": slug,
                "status": item.get("status"),
                "link": item.get("link"),
                "date": item.get("date"),
                "modified": item.get("modified"),
                "modified_gmt": item.get("modified_gmt"),
                "acf": item.get("acf"),
                "meta": item.get("meta"),
                "relationships": relationships,
            }
        }

        content_text = self._extract_text(item)
        raw_json = json.dumps(item, indent=2, default=str)
        # Preserve raw payload for debugging/structured retrieval.
        metadata["wordpress"]["raw"] = raw_json

        return LoadedDocument(
            content=content_text,
            source=self.source_name,
            source_id=f"{endpoint}/{item_id}",
            filename=f"{endpoint}_{slug}.txt",
            metadata=metadata,
            created_at=created,
            modified_at=modified,
        )

    # ---------------------------------------------------------------------
    # BaseLoader interface
    # ---------------------------------------------------------------------

    def load_document(self, doc_id: str) -> Optional[LoadedDocument]:
        """Load a single WordPress resource.

        `doc_id` should be in the form "posts/123" or "pages/456".
        """

        self._ensure_authenticated()

        try:
            endpoint, resource_id = doc_id.split("/", 1)
            item = self._get(f"{endpoint}/{resource_id}")
            if not isinstance(item, dict):
                raise TypeError("Expected dict response")
            return self._to_loaded_document(endpoint, item)
        except Exception as e:
            logger.error(f"Failed to load WordPress document {doc_id}: {e}")
            return None

    def load_folder(
        self, folder_path: str, recursive: bool = True
    ) -> list[LoadedDocument]:
        """Load all documents from a content endpoint.

        Examples:
            - folder_path="posts"
            - folder_path="pages"
            - folder_path="my_custom_type" (if exposed via REST)
        """

        self._ensure_authenticated()
        endpoint = folder_path.strip("/")
        docs: list[LoadedDocument] = []

        try:
            params = {"status": self.default_status}
            items = self._list_paginated(endpoint, params=params)
            for item in items:
                if isinstance(item, dict):
                    docs.append(self._to_loaded_document(endpoint, item))
        except Exception as e:
            logger.error(f"Failed to load WordPress {folder_path}: {e}")

        return docs

    def search(self, query: str, max_results: int = 50) -> list[LoadedDocument]:
        """Search WordPress content via the REST API search endpoint."""

        self._ensure_authenticated()
        docs: list[LoadedDocument] = []

        try:
            items = self._get(
                "search", params={"search": query, "per_page": max_results}
            )
            if not isinstance(items, list):
                return []

            # `/search` returns a lighter payload; fetch the real entity for ingest.
            for hit in items:
                if not isinstance(hit, dict):
                    continue
                hit_type = hit.get("type")
                hit_id = hit.get("id")
                if hit_type and hit_id:
                    doc = self.load_document(f"{hit_type}/{hit_id}")
                    if doc:
                        docs.append(doc)
        except Exception as e:
            logger.error(f"WordPress search failed: {e}")

        return docs

    # ---------------------------------------------------------------------
    # Incremental sync helpers
    # ---------------------------------------------------------------------

    def load_since(
        self,
        since: datetime,
        *,
        endpoints: tuple[str, ...] = ("posts", "pages"),
        include_unpublished: bool = False,
        per_page: int = 100,
        max_pages: int = 50,
    ) -> list[LoadedDocument]:
        """Incremental sync: load content modified since a timestamp."""

        self._ensure_authenticated()
        docs: list[LoadedDocument] = []
        since_utc = since.astimezone(UTC)

        for endpoint in endpoints:
            params: dict[str, Any] = {
                "per_page": per_page,
                "status": "any" if include_unpublished else self.default_status,
                "modified_after": since_utc.isoformat(),
            }

            try:
                items = self._list_paginated(
                    endpoint, params=params, per_page=per_page, max_pages=max_pages
                )
                for item in items:
                    if isinstance(item, dict):
                        docs.append(self._to_loaded_document(endpoint, item))
            except Exception:
                # Fallback: some WP installs might not support modified_after.
                params.pop("modified_after", None)
                params["after"] = since_utc.isoformat()
                try:
                    items = self._list_paginated(
                        endpoint, params=params, per_page=per_page, max_pages=max_pages
                    )
                    for item in items:
                        if isinstance(item, dict):
                            docs.append(self._to_loaded_document(endpoint, item))
                except Exception as e:
                    logger.error(f"Incremental sync failed for {endpoint}: {e}")

        return docs


__all__ = ["WordPressLoader"]
