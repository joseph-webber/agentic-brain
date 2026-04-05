# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""GitHub repository connector."""

from __future__ import annotations

import base64
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Mapping

from .base import (
    Connector,
    ConnectorRecord,
    ConnectorSyncCursor,
    ConnectorSyncPage,
    parse_datetime,
)


class GitHubConnector(Connector):
    CODE_EXTENSIONS = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".cs",
        ".swift",
        ".kt",
        ".sh",
        ".bash",
        ".zsh",
        ".ps1",
        ".sql",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".m",
        ".mm",
        ".yaml",
        ".yml",
        ".json",
        ".toml",
        ".ini",
        ".cfg",
        ".conf",
        ".md",
        ".txt",
        ".rst",
        ".html",
        ".htm",
    }

    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        token: str | None = None,
        branch: str = "main",
        path: str = "",
        page_size: int = 100,
        client=None,
        base_url: str = "https://api.github.com",
    ) -> None:
        super().__init__(page_size=page_size, client=client)
        self.owner = owner
        self.repo = repo
        self.token = token
        self.branch = branch
        self.path = path.strip("/")
        self.base_url = base_url.rstrip("/")

    @property
    def source_name(self) -> str:
        return "github"

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def authenticate(self) -> bool:
        return bool(self.owner and self.repo)

    def _include_path(self, path: str, *, size: int = 0) -> bool:
        if PurePosixPath(path).name.lower() in {
            "readme",
            "license",
            "changelog",
            "contributing",
            "makefile",
            "dockerfile",
        }:
            return True
        suffix = PurePosixPath(path).suffix.lower()
        if suffix in self.CODE_EXTENSIONS:
            return True
        return size > 0 and suffix == ""

    def _content_to_record(self, payload: Mapping[str, Any]) -> ConnectorRecord | None:
        if payload.get("type") != "file":
            return None
        path = str(payload.get("path") or payload.get("name") or "")
        if not self._include_path(path, size=int(payload.get("size") or 0)):
            return None
        content = payload.get("content")
        if content and payload.get("encoding") == "base64":
            content_text = base64.b64decode(str(content).encode()).decode(
                "utf-8", errors="replace"
            )
        elif isinstance(content, str):
            content_text = content
        else:
            download_url = payload.get("download_url")
            if not download_url:
                return None
            content_text = self._request_text(
                "GET", str(download_url), headers=self._headers
            )
        updated_at = parse_datetime(
            payload.get("last_modified") or payload.get("updated_at")
        )
        return ConnectorRecord(
            source=self.source_name,
            id=path,
            title=str(payload.get("name") or PurePosixPath(path).name),
            content=content_text,
            url=str(payload.get("html_url") or payload.get("url") or ""),
            updated_at=updated_at,
            metadata={
                "repository": f"{self.owner}/{self.repo}",
                "path": path,
                "sha": payload.get("sha"),
                "mime_type": payload.get("type"),
            },
        )

    def list_changes(
        self,
        *,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncPage:
        limit = limit or self.page_size
        repo = self._request_json(
            "GET",
            f"{self.base_url}/repos/{self.owner}/{self.repo}",
            headers=self._headers,
        )
        branch = str(repo.get("default_branch") or self.branch)
        tree = self._request_json(
            "GET",
            f"{self.base_url}/repos/{self.owner}/{self.repo}/git/trees/{branch}",
            headers=self._headers,
            params={"recursive": 1},
        )
        current_sha = str(tree.get("sha") or "")
        previous_sha = cursor.state.get("tree_sha") if cursor else None
        if previous_sha and previous_sha == current_sha:
            return ConnectorSyncPage(
                items=[],
                next_cursor=ConnectorSyncCursor(
                    updated_after=cursor.updated_after if cursor else None,
                    page_token=current_sha,
                    state={"tree_sha": current_sha},
                ),
                has_more=False,
                state={"tree_sha": current_sha},
            )

        records: list[ConnectorRecord] = []
        latest: datetime | None = cursor.updated_after if cursor else None
        for entry in tree.get("tree", []):
            if len(records) >= limit:
                break
            if entry.get("type") != "blob":
                continue
            path = str(entry.get("path") or "")
            if self.path and not (
                path == self.path or path.startswith(self.path.rstrip("/") + "/")
            ):
                continue
            if not self._include_path(path, size=int(entry.get("size") or 0)):
                continue
            payload = self._request_json(
                "GET",
                f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{path}",
                headers=self._headers,
                params={"ref": branch},
            )
            if isinstance(payload, list):
                continue
            record = self._content_to_record(payload)
            if record:
                records.append(record)
                latest = max(
                    [d for d in [latest, record.updated_at] if d is not None],
                    default=latest,
                )
        return ConnectorSyncPage(
            items=records,
            next_cursor=ConnectorSyncCursor(
                updated_after=latest,
                page_token=current_sha,
                state={"tree_sha": current_sha, "branch": branch},
            ),
            has_more=len(records) >= limit,
            state={"tree_sha": current_sha, "branch": branch},
        )

    def fetch_item(self, item_id: str) -> ConnectorRecord | None:
        try:
            payload = self._request_json(
                "GET",
                f"{self.base_url}/repos/{self.owner}/{self.repo}/contents/{item_id}",
                headers=self._headers,
                params={"ref": self.branch},
            )
            if isinstance(payload, list):
                return None
            return self._content_to_record(payload)
        except Exception:
            return None
