# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Base connector abstractions and sync helpers."""

from __future__ import annotations

import html
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping, MutableMapping

import httpx

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(UTC)


def parse_datetime(value: Any) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


@dataclass(slots=True)
class ConnectorRecord:
    """Normalized record returned by a connector."""

    source: str
    id: str
    title: str = ""
    content: str = ""
    url: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    deleted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "deleted": self.deleted,
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class ConnectorSyncCursor:
    """Incremental sync cursor."""

    updated_after: datetime | None = None
    page_token: str = ""
    etag: str = ""
    state: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "updated_after": self.updated_after.isoformat()
            if self.updated_after
            else None,
            "page_token": self.page_token,
            "etag": self.etag,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ConnectorSyncCursor:
        return cls(
            updated_after=parse_datetime(data.get("updated_after")),
            page_token=str(data.get("page_token") or ""),
            etag=str(data.get("etag") or ""),
            state=dict(data.get("state") or {}),
        )


@dataclass(slots=True)
class ConnectorSchedule:
    """Polling schedule for sync jobs."""

    interval: timedelta = timedelta(hours=1)
    enabled: bool = True
    immediate: bool = False
    jitter: timedelta = timedelta(0)

    def next_run_at(
        self, last_run: datetime | None = None, *, now: datetime | None = None
    ) -> datetime | None:
        if not self.enabled:
            return None
        now = now or utcnow()
        if self.immediate and last_run is None:
            return now
        return now + self.interval + self.jitter

    def is_due(
        self, last_run: datetime | None = None, *, now: datetime | None = None
    ) -> bool:
        if not self.enabled:
            return False
        now = now or utcnow()
        if self.immediate and last_run is None:
            return True
        if last_run is None:
            return True
        return now >= self.next_run_at(last_run, now=last_run)


@dataclass(slots=True)
class ConnectorSyncPage:
    """One page of sync results."""

    items: list[ConnectorRecord] = field(default_factory=list)
    next_cursor: ConnectorSyncCursor | None = None
    has_more: bool = False
    state: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConnectorSyncResult:
    """Result of a sync run."""

    source: str
    items: list[ConnectorRecord]
    cursor: ConnectorSyncCursor
    fetched_at: datetime
    changed_count: int
    next_run_at: datetime | None
    full_refresh: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "items": [item.to_dict() for item in self.items],
            "cursor": self.cursor.to_dict(),
            "fetched_at": self.fetched_at.isoformat(),
            "changed_count": self.changed_count,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "full_refresh": self.full_refresh,
        }


class Connector(ABC):
    """Abstract base class for connectors."""

    def __init__(
        self,
        *,
        schedule: ConnectorSchedule | None = None,
        page_size: int = 100,
        client: httpx.Client | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.schedule = schedule or ConnectorSchedule()
        self.page_size = max(1, page_size)
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the connector source name."""

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate or validate the connection."""

    @abstractmethod
    def list_changes(
        self,
        *,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncPage:
        """Return the next page of changed records."""

    @abstractmethod
    def fetch_item(self, item_id: str) -> ConnectorRecord | None:
        """Fetch a single item by identifier."""

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> Connector:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> dict[str, Any]:
        response = self._client.request(
            method, url, headers=headers, params=params, json=json
        )
        response.raise_for_status()
        if not response.content:
            return {}
        return response.json()

    def _request_text(
        self,
        method: str,
        url: str,
        *,
        headers: Mapping[str, str] | None = None,
        params: Mapping[str, Any] | None = None,
        json: Any = None,
    ) -> str:
        response = self._client.request(
            method, url, headers=headers, params=params, json=json
        )
        response.raise_for_status()
        return response.text

    @staticmethod
    def _dedupe(records: list[ConnectorRecord]) -> list[ConnectorRecord]:
        seen: set[tuple[str, str]] = set()
        deduped: list[ConnectorRecord] = []
        for record in records:
            key = (record.source, record.id)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(record)
        return deduped

    @staticmethod
    def _max_timestamp(
        records: list[ConnectorRecord], fallback: datetime | None = None
    ) -> datetime | None:
        candidates = [
            ts
            for record in records
            for ts in (record.updated_at, record.created_at)
            if ts is not None
        ]
        if candidates:
            return max(candidates)
        return fallback

    def _merge_cursor(
        self,
        cursor: ConnectorSyncCursor | None,
        page: ConnectorSyncPage,
        records: list[ConnectorRecord],
    ) -> ConnectorSyncCursor:
        base = cursor or ConnectorSyncCursor()
        state: MutableMapping[str, Any] = dict(base.state)
        state.update(page.state)
        next_cursor = page.next_cursor or ConnectorSyncCursor()
        updated_after = self._max_timestamp(records, base.updated_after)
        if next_cursor.updated_after and (
            updated_after is None or next_cursor.updated_after > updated_after
        ):
            updated_after = next_cursor.updated_after
        return ConnectorSyncCursor(
            updated_after=updated_after,
            page_token=next_cursor.page_token or base.page_token,
            etag=next_cursor.etag or base.etag,
            state=dict(state),
        )

    def sync(
        self,
        *,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncResult:
        if not self.authenticate():
            raise RuntimeError(f"Failed to authenticate {self.source_name}")
        now = utcnow()
        page = self.list_changes(cursor=cursor, limit=limit or self.page_size)
        items = self._dedupe(page.items)
        next_cursor = self._merge_cursor(cursor, page, items)
        return ConnectorSyncResult(
            source=self.source_name,
            items=items,
            cursor=next_cursor,
            fetched_at=now,
            changed_count=len(items),
            next_run_at=self.schedule.next_run_at(now, now=now),
            full_refresh=cursor is None or cursor.updated_after is None,
        )

    def incremental_sync(
        self,
        *,
        since: datetime | None = None,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncResult:
        sync_cursor = cursor or ConnectorSyncCursor(updated_after=since)
        if since and sync_cursor.updated_after is None:
            sync_cursor.updated_after = since
        return self.sync(cursor=sync_cursor, limit=limit)

    def should_sync(
        self, last_run: datetime | None = None, *, now: datetime | None = None
    ) -> bool:
        return self.schedule.is_due(last_run, now=now)

    def next_run_at(
        self, last_run: datetime | None = None, *, now: datetime | None = None
    ) -> datetime | None:
        return self.schedule.next_run_at(last_run, now=now)

    def normalize_text(self, value: str | None) -> str:
        return html.unescape(value or "").strip()
