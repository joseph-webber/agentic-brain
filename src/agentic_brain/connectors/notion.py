# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Notion connector."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Mapping

from .base import (
    Connector,
    ConnectorRecord,
    ConnectorSyncCursor,
    ConnectorSyncPage,
    parse_datetime,
)


def _rich_text_to_text(rich_text: list[Mapping[str, Any]] | None) -> str:
    parts: list[str] = []
    for entry in rich_text or []:
        parts.append(
            str(entry.get("plain_text") or entry.get("text", {}).get("content", ""))
        )
    return "".join(parts).strip()


class NotionConnector(Connector):
    def __init__(
        self,
        token: str,
        *,
        database_id: str | None = None,
        page_size: int = 100,
        client=None,
        base_url: str = "https://api.notion.com/v1",
        notion_version: str = "2022-06-28",
    ) -> None:
        super().__init__(page_size=page_size, client=client)
        self.token = token
        self.database_id = database_id
        self.base_url = base_url.rstrip("/")
        self.notion_version = notion_version

    @property
    def source_name(self) -> str:
        return "notion"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": self.notion_version,
            "Content-Type": "application/json",
        }

    def authenticate(self) -> bool:
        return bool(self.token)

    def _page_title(self, page: Mapping[str, Any]) -> str:
        properties = page.get("properties", {}) if isinstance(page, Mapping) else {}
        for prop in properties.values():
            if isinstance(prop, Mapping) and prop.get("type") == "title":
                return _rich_text_to_text(prop.get("title"))
        return str(page.get("title") or page.get("id") or "")

    def _block_lines(self, block: Mapping[str, Any], depth: int = 0) -> list[str]:
        block_type = block.get("type")
        payload = block.get(block_type, {}) if block_type else {}
        prefix = "  " * depth
        text = ""
        if isinstance(payload, Mapping):
            if "rich_text" in payload:
                text = _rich_text_to_text(payload.get("rich_text"))
            elif "text" in payload:
                text = _rich_text_to_text(payload.get("text"))
        if block_type in {"heading_1", "heading_2", "heading_3"}:
            text = text.upper()
        lines = [f"{prefix}{text}".rstrip() if text else ""]
        if block.get("has_children"):
            child_id = block.get("id")
            if child_id:
                child_response = self._request_json(
                    "GET",
                    f"{self.base_url}/blocks/{child_id}/children",
                    headers=self._headers,
                )
                for child in child_response.get("results", []):
                    lines.extend(self._block_lines(child, depth + 1))
        return [line for line in lines if line]

    def _page_content(self, page_id: str) -> str:
        blocks = self._request_json(
            "GET",
            f"{self.base_url}/blocks/{page_id}/children",
            headers=self._headers,
        )
        lines: list[str] = []
        for block in blocks.get("results", []):
            lines.extend(self._block_lines(block))
        return "\n".join(lines).strip()

    def _page_to_record(
        self, page: Mapping[str, Any], content: str | None = None
    ) -> ConnectorRecord:
        title = self._page_title(page)
        updated_at = parse_datetime(page.get("last_edited_time")) or parse_datetime(
            page.get("edited_time")
        )
        created_at = parse_datetime(page.get("created_time"))
        return ConnectorRecord(
            source=self.source_name,
            id=str(page.get("id") or title),
            title=title,
            content=content if content is not None else title,
            url=str(page.get("url") or ""),
            created_at=created_at,
            updated_at=updated_at,
            metadata={
                "archived": bool(page.get("archived", False)),
                "parent": page.get("parent", {}),
                "properties": list(page.get("properties", {}).keys()),
            },
        )

    def list_changes(
        self,
        *,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncPage:
        limit = limit or self.page_size
        since = cursor.updated_after if cursor else None
        body: dict[str, Any] = {"page_size": limit}
        if self.database_id and since:
            body["filter"] = {
                "timestamp": "last_edited_time",
                "last_edited_time": {"after": since.isoformat()},
            }

        if self.database_id:
            response = self._request_json(
                "POST",
                f"{self.base_url}/databases/{self.database_id}/query",
                headers=self._headers,
                json=body,
            )
            results = response.get("results", [])
        else:
            response = self._request_json(
                "POST",
                f"{self.base_url}/search",
                headers=self._headers,
                json=body,
            )
            results = [
                item
                for item in response.get("results", [])
                if item.get("object") == "page"
            ]
            if since:
                results = [
                    item
                    for item in results
                    if (
                        parse_datetime(item.get("last_edited_time"))
                        or datetime.min.replace(tzinfo=UTC)
                    )
                    > since
                ]

        records: list[ConnectorRecord] = []
        latest: datetime | None = since
        for page in results:
            record = self._page_to_record(page)
            records.append(record)
            latest = max(
                [
                    d
                    for d in [latest, record.updated_at, record.created_at]
                    if d is not None
                ],
                default=latest,
            )

        next_cursor = ConnectorSyncCursor(
            updated_after=latest,
            page_token=str(response.get("next_cursor") or ""),
            state={"has_more": bool(response.get("has_more", False))},
        )
        return ConnectorSyncPage(
            items=records,
            next_cursor=next_cursor,
            has_more=bool(response.get("has_more", False)),
            state={"query": "database" if self.database_id else "search"},
        )

    def fetch_item(self, item_id: str) -> ConnectorRecord | None:
        try:
            page = self._request_json(
                "GET", f"{self.base_url}/pages/{item_id}", headers=self._headers
            )
            content = self._page_content(item_id)
            return self._page_to_record(page, content=content or self._page_title(page))
        except Exception:
            return None
