# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Google Drive connector."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from .base import (
    Connector,
    ConnectorRecord,
    ConnectorSyncCursor,
    ConnectorSyncPage,
    parse_datetime,
)


class GoogleDriveConnector(Connector):
    GOOGLE_EXPORTS = {
        "application/vnd.google-apps.document": "text/plain",
        "application/vnd.google-apps.spreadsheet": "text/csv",
        "application/vnd.google-apps.presentation": "text/plain",
    }

    def __init__(
        self,
        token: str,
        *,
        folder_id: str | None = None,
        drive_id: str | None = None,
        page_size: int = 100,
        client=None,
        base_url: str = "https://www.googleapis.com/drive/v3",
    ) -> None:
        super().__init__(page_size=page_size, client=client)
        self.token = token
        self.folder_id = folder_id
        self.drive_id = drive_id
        self.base_url = base_url.rstrip("/")

    @property
    def source_name(self) -> str:
        return "google_drive"

    @property
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    def authenticate(self) -> bool:
        return bool(self.token)

    def _query(self, cursor: ConnectorSyncCursor | None = None) -> str:
        parts = ["trashed = false"]
        if self.folder_id:
            parts.append(f"'{self.folder_id}' in parents")
        if cursor and cursor.updated_after:
            parts.append(f"modifiedTime > '{cursor.updated_after.isoformat()}'")
        return " and ".join(parts)

    def _file_to_record(
        self, payload: Mapping[str, Any], content: str
    ) -> ConnectorRecord:
        return ConnectorRecord(
            source=self.source_name,
            id=str(payload.get("id") or ""),
            title=str(payload.get("name") or payload.get("id") or ""),
            content=content,
            url=str(payload.get("webViewLink") or payload.get("webContentLink") or ""),
            created_at=parse_datetime(payload.get("createdTime")),
            updated_at=parse_datetime(payload.get("modifiedTime")),
            metadata={
                "mime_type": payload.get("mimeType"),
                "parents": list(payload.get("parents") or []),
                "size": payload.get("size"),
            },
        )

    def _load_file_content(self, file_id: str, mime_type: str) -> str:
        if mime_type in self.GOOGLE_EXPORTS:
            export_mime = self.GOOGLE_EXPORTS[mime_type]
            return self._request_text(
                "GET",
                f"{self.base_url}/files/{file_id}/export",
                headers=self._headers,
                params={"mimeType": export_mime},
            )
        response = self._client.request(
            "GET",
            f"{self.base_url}/files/{file_id}",
            headers=self._headers,
            params={"alt": "media"},
        )
        response.raise_for_status()
        if response.content:
            return response.content.decode("utf-8", errors="replace")
        return response.text

    def list_changes(
        self,
        *,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncPage:
        limit = limit or self.page_size
        query = self._query(cursor)
        response = self._request_json(
            "GET",
            f"{self.base_url}/files",
            headers=self._headers,
            params={
                "q": query,
                "pageSize": limit,
                "fields": "files(id,name,mimeType,createdTime,modifiedTime,parents,size,webViewLink,webContentLink),nextPageToken",
                "supportsAllDrives": "true",
                "includeItemsFromAllDrives": "true",
            },
        )
        records: list[ConnectorRecord] = []
        latest: datetime | None = cursor.updated_after if cursor else None
        for file in response.get("files", []):
            content = self._load_file_content(
                str(file.get("id")), str(file.get("mimeType") or "")
            )
            record = self._file_to_record(file, content)
            records.append(record)
            latest = max(
                [d for d in [latest, record.updated_at] if d is not None],
                default=latest,
            )
        return ConnectorSyncPage(
            items=records,
            next_cursor=ConnectorSyncCursor(
                updated_after=latest,
                page_token=str(response.get("nextPageToken") or ""),
                state={"q": query},
            ),
            has_more=bool(response.get("nextPageToken")),
            state={"q": query},
        )

    def fetch_item(self, item_id: str) -> ConnectorRecord | None:
        try:
            payload = self._request_json(
                "GET",
                f"{self.base_url}/files/{item_id}",
                headers=self._headers,
                params={
                    "fields": "id,name,mimeType,createdTime,modifiedTime,parents,size,webViewLink,webContentLink"
                },
            )
            content = self._load_file_content(
                item_id, str(payload.get("mimeType") or "")
            )
            return self._file_to_record(payload, content)
        except Exception:
            return None
