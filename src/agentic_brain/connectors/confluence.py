# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Confluence connector."""

from __future__ import annotations

import base64
import html as html_module
import re
from typing import Any, Mapping

from .base import (
    Connector,
    ConnectorRecord,
    ConnectorSyncCursor,
    ConnectorSyncPage,
    parse_datetime,
)


class ConfluenceConnector(Connector):
    def __init__(
        self,
        base_url: str,
        *,
        username: str,
        api_token: str,
        space_key: str | None = None,
        page_size: int = 100,
        client=None,
    ) -> None:
        super().__init__(page_size=page_size, client=client)
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.api_token = api_token
        self.space_key = space_key

    @property
    def source_name(self) -> str:
        return "confluence"

    @property
    def _headers(self) -> dict[str, str]:
        token = base64.b64encode(f"{self.username}:{self.api_token}".encode()).decode()
        return {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def authenticate(self) -> bool:
        return bool(self.base_url and self.username and self.api_token)

    def _strip_html(self, value: str) -> str:
        plain = re.sub(r"<[^>]+>", " ", value)
        return re.sub(r"\s+", " ", html_module.unescape(plain)).strip()

    def _page_to_record(self, page: Mapping[str, Any]) -> ConnectorRecord:
        body = page.get("body", {}).get("storage", {}).get("value", "")
        version = page.get("version", {})
        title = str(page.get("title") or page.get("id") or "")
        return ConnectorRecord(
            source=self.source_name,
            id=str(page.get("id") or title),
            title=title,
            content=self._strip_html(str(body)),
            url=str(page.get("_links", {}).get("webui") or page.get("url") or ""),
            created_at=parse_datetime(page.get("history", {}).get("createdDate")),
            updated_at=parse_datetime(version.get("when"))
            or parse_datetime(page.get("lastModified")),
            metadata={
                "space_key": page.get("space", {}).get("key"),
                "version": version.get("number"),
                "status": page.get("status"),
            },
        )

    def list_changes(
        self,
        *,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncPage:
        limit = limit or self.page_size
        params: dict[str, Any] = {
            "limit": limit,
            "expand": "version,space,body.storage,history",
        }
        cql_parts = ["type = page"]
        if self.space_key:
            cql_parts.append(f'space = "{self.space_key}"')
        if cursor and cursor.updated_after:
            cql_parts.append(f'lastmodified > "{cursor.updated_after.isoformat()}"')
        params["cql"] = " AND ".join(cql_parts)
        response = self._request_json(
            "GET",
            f"{self.base_url}/rest/api/content/search",
            headers=self._headers,
            params=params,
        )
        results = response.get("results", [])
        records = [self._page_to_record(page) for page in results]
        latest = max(
            (r.updated_at for r in records if r.updated_at),
            default=cursor.updated_after if cursor else None,
        )
        next_cursor = ConnectorSyncCursor(
            updated_after=latest,
            page_token=str(response.get("_links", {}).get("next") or ""),
            state={"size": response.get("size", len(records))},
        )
        return ConnectorSyncPage(
            items=records,
            next_cursor=next_cursor,
            has_more=bool(response.get("_links", {}).get("next")),
        )

    def fetch_item(self, item_id: str) -> ConnectorRecord | None:
        try:
            page = self._request_json(
                "GET",
                f"{self.base_url}/rest/api/content/{item_id}",
                headers=self._headers,
                params={"expand": "body.storage,version,space,history"},
            )
            return self._page_to_record(page)
        except Exception:
            return None

    def search(self, cql: str, *, limit: int = 100) -> list[ConnectorRecord]:
        params = {
            "cql": cql,
            "limit": limit,
            "expand": "version,space,body.storage,history",
        }
        response = self._request_json(
            "GET",
            f"{self.base_url}/rest/api/content/search",
            headers=self._headers,
            params=params,
        )
        return [self._page_to_record(page) for page in response.get("results", [])]
