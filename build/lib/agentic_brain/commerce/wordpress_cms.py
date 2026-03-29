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

"""Headless WordPress CMS integration.

This module builds on :class:`~agentic_brain.commerce.wordpress.WordPressClient` by
providing "headless CMS" features oriented around RAG ingestion:

- REST API v2 access (GET/POST/PUT/PATCH/DELETE)
- Gutenberg block parsing (from content HTML)
- ACF field preservation (when exposed via ACF-to-REST-API or similar)
- Optional GraphQL access via the WPGraphQL plugin
- Sync helpers to push WordPress content into a RAG DocumentStore

The RAG loader (`agentic_brain.rag.loaders.wordpress.WordPressLoader`) is the
primary ingestion entrypoint for most pipelines. This module exists for richer
content parsing + headless CMS workflows.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

import aiohttp

from .wordpress import WPAuth

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gutenberg parsing
# ---------------------------------------------------------------------------


_BLOCK_RE = re.compile(
    r"<!--\s*(?P<closing>/)?wp:(?P<name>[a-zA-Z0-9_\-/]+)"
    r"(?:\s+(?P<attrs>\{.*?\}))?\s*(?P<selfclose>/)?\s*-->",
    flags=re.DOTALL,
)


def _html_to_text(value: str) -> str:
    """Best-effort HTML to text.

    We keep this dependency-light; BeautifulSoup is used when installed.
    """

    if not value:
        return ""

    try:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(value, "html.parser")
        for element in soup(["script", "style", "head", "meta", "link"]):
            element.decompose()
        text = soup.get_text(separator="\n")
        lines = (line.strip() for line in text.splitlines())
        return "\n".join(line for line in lines if line)
    except Exception:
        # Basic fallback that is good enough for RAG ingestion.
        text = re.sub(
            r"<script[^>]*>.*?</script>", "", value, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()


@dataclass
class GutenbergBlock:
    """A parsed Gutenberg block."""

    name: str
    attrs: dict[str, Any] = field(default_factory=dict)
    inner_html: str = ""
    inner_text: str = ""
    inner_blocks: list[GutenbergBlock] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "attrs": self.attrs,
            "inner_html": self.inner_html,
            "inner_text": self.inner_text,
            "inner_blocks": [b.to_dict() for b in self.inner_blocks],
        }


class GutenbergParser:
    """Parse Gutenberg blocks embedded in post content HTML."""

    @classmethod
    def parse(cls, html: str) -> list[GutenbergBlock]:
        """Parse Gutenberg blocks from HTML.

        Gutenberg stores blocks in HTML comments, e.g.:

            <!-- wp:paragraph {"align":"center"} -->Hello<!-- /wp:paragraph -->
            <!-- wp:image {"id":123} /-->

        This parser is resilient: if content doesn't contain valid blocks it
        returns an empty list.
        """

        if not html:
            return []

        matches = list(_BLOCK_RE.finditer(html))
        if not matches:
            return []

        blocks: list[GutenbergBlock] = []
        stack: list[tuple[GutenbergBlock, int]] = []  # (block, inner_start_index)

        for match in matches:
            name = match.group("name") or ""
            is_closing = bool(match.group("closing"))
            is_selfclose = bool(match.group("selfclose"))

            attrs: dict[str, Any] = {}
            attrs_raw = match.group("attrs")
            if attrs_raw:
                try:
                    attrs = json.loads(attrs_raw)
                except json.JSONDecodeError:
                    attrs = {"_raw": attrs_raw}

            if is_closing:
                # Pop the last matching opener. If mismatched, ignore.
                for i in range(len(stack) - 1, -1, -1):
                    open_block, inner_start = stack[i]
                    if open_block.name == name:
                        inner_html = html[inner_start : match.start()]
                        open_block.inner_html = inner_html
                        open_block.inner_text = _html_to_text(inner_html)
                        stack = stack[:i]
                        break
                continue

            new_block = GutenbergBlock(name=name, attrs=attrs)

            if is_selfclose:
                new_block.inner_html = ""
                new_block.inner_text = ""
                if stack:
                    stack[-1][0].inner_blocks.append(new_block)
                else:
                    blocks.append(new_block)
                continue

            # Opening tag
            inner_start = match.end()
            if stack:
                stack[-1][0].inner_blocks.append(new_block)
            else:
                blocks.append(new_block)
            stack.append((new_block, inner_start))

        return blocks


# ---------------------------------------------------------------------------
# Headless CMS API
# ---------------------------------------------------------------------------


def _parse_wp_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed
    except ValueError:
        return None


class HeadlessCMS:
    """Headless WordPress CMS client.

    This is an async-first client designed to:

    1. Read and write WordPress content via REST API v2.
    2. Optionally query WPGraphQL for richer relationships.
    3. Provide helpers to sync posts/pages/CPTs into a RAG document store.

    Notes:
        - For authentication, prefer WordPress "Application Passwords".
        - To expose ACF fields, install an ACF REST integration plugin.
    """

    def __init__(
        self,
        auth: WPAuth,
        *,
        graphql_endpoint: str | None = None,
        session: aiohttp.ClientSession | None = None,
    ):
        self.auth = auth
        self.graphql_endpoint = graphql_endpoint or f"{auth.base_url}/graphql"
        self._session = session
        self._owns_session = session is None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers=self.auth.headers(),
                auth=self.auth.basic_auth(),
                timeout=aiohttp.ClientTimeout(total=self.auth.timeout),
            )
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> HeadlessCMS:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    def _rest_url(self, endpoint: str) -> str:
        endpoint = endpoint.lstrip("/")
        return f"{self.auth.rest_base_url}/{endpoint}"

    async def rest_request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        json_body: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """Perform a REST API request."""

        session = await self._get_session()
        url = self._rest_url(endpoint)
        req_headers: MutableMapping[str, str] = {}
        if headers:
            req_headers.update(headers)

        async with session.request(
            method.upper(),
            url,
            params=dict(params) if params else None,
            json=json_body,
            headers=req_headers or None,
        ) as response:
            response.raise_for_status()
            # WP REST is JSON; errors here indicate plugins returning HTML.
            return await response.json()

    async def rest_get(
        self, endpoint: str, *, params: Mapping[str, Any] | None = None
    ) -> Any:
        return await self.rest_request("GET", endpoint, params=params)

    async def rest_list_paginated(
        self,
        endpoint: str,
        *,
        params: Mapping[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int = 50,
    ) -> list[dict[str, Any]]:
        """Fetch a paginated REST collection."""

        out: list[dict[str, Any]] = []
        base_params: dict[str, Any] = dict(params) if params else {}
        base_params.setdefault("per_page", per_page)

        for page in range(1, max_pages + 1):
            page_params = dict(base_params)
            page_params["page"] = page
            batch = await self.rest_get(endpoint, params=page_params)

            if not isinstance(batch, list):
                raise TypeError(
                    f"Expected list response for {endpoint}, got {type(batch)}"
                )
            if not batch:
                break
            out.extend(batch)
            if len(batch) < per_page:
                break

        return out

    async def graphql_query(
        self,
        query: str,
        *,
        variables: Mapping[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> Any:
        """Execute a GraphQL query via WPGraphQL."""

        session = await self._get_session()
        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = dict(variables)
        if operation_name is not None:
            payload["operationName"] = operation_name

        async with session.post(self.graphql_endpoint, json=payload) as response:
            response.raise_for_status()
            data = await response.json()

        if isinstance(data, dict) and data.get("errors"):
            raise RuntimeError(f"WPGraphQL returned errors: {data['errors']}")
        return data

    # ---------------------------------------------------------------------
    # RAG sync helpers
    # ---------------------------------------------------------------------

    def _item_to_rag_text(self, item: Mapping[str, Any]) -> str:
        title_html = (item.get("title") or {}).get("rendered") or ""
        excerpt_html = (item.get("excerpt") or {}).get("rendered") or ""
        content_html = (item.get("content") or {}).get("rendered") or ""

        blocks = GutenbergParser.parse(content_html)
        if blocks:
            body_text = "\n\n".join(b.inner_text for b in blocks if b.inner_text)
        else:
            body_text = _html_to_text(content_html)

        parts = [
            _html_to_text(title_html).strip(),
            _html_to_text(excerpt_html).strip(),
            body_text.strip(),
        ]
        return "\n\n".join(p for p in parts if p)

    def _item_relationships(self, item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "author": item.get("author"),
            "parent": item.get("parent"),
            "featured_media": item.get("featured_media"),
            "categories": item.get("categories"),
            "tags": item.get("tags"),
            "menu_order": item.get("menu_order"),
            "_links": item.get("_links"),
        }

    async def sync_to_document_store(
        self,
        store: Any,
        *,
        endpoints: Sequence[str] = ("posts", "pages"),
        since: datetime | None = None,
        include_unpublished: bool = False,
        include_embed: bool = True,
        extra_params: Mapping[str, Any] | None = None,
        per_page: int = 100,
        max_pages: int = 50,
    ) -> list[str]:
        """Sync WordPress content into a RAG document store.

        The document store is expected to implement a `add(content, metadata, doc_id)`
        method (compatible with :class:`agentic_brain.rag.store.DocumentStore`).
        """

        doc_ids: list[str] = []
        for endpoint in endpoints:
            params: dict[str, Any] = dict(extra_params) if extra_params else {}
            params.setdefault("status", "any" if include_unpublished else "publish")
            if include_embed:
                params.setdefault("_embed", "1")
            if since is not None:
                # WordPress supports modified_after on many endpoints.
                params.setdefault("modified_after", since.astimezone(UTC).isoformat())

            items = await self.rest_list_paginated(
                endpoint,
                params=params,
                per_page=per_page,
                max_pages=max_pages,
            )

            for item in items:
                item_id = item.get("id")
                if item_id is None:
                    continue

                doc_id = f"wordpress:{self.auth.base_url}:{endpoint}:{item_id}"

                metadata = {
                    "wordpress": {
                        "site": self.auth.base_url,
                        "endpoint": endpoint,
                        "id": item_id,
                        "slug": item.get("slug"),
                        "status": item.get("status"),
                        "link": item.get("link"),
                        "date": item.get("date"),
                        "modified": item.get("modified"),
                        "modified_gmt": item.get("modified_gmt"),
                        "acf": item.get("acf"),
                        "meta": item.get("meta"),
                        "relationships": self._item_relationships(item),
                    }
                }

                modified = _parse_wp_datetime(
                    item.get("modified_gmt") or item.get("modified")
                )
                if modified is not None:
                    metadata["wordpress"]["modified_at"] = modified.isoformat()

                content = self._item_to_rag_text(item)

                store.add(content, metadata=metadata, doc_id=doc_id)
                doc_ids.append(doc_id)

        logger.info("Synced %d WordPress documents", len(doc_ids))
        return doc_ids


__all__ = [
    "GutenbergBlock",
    "GutenbergParser",
    "HeadlessCMS",
]
