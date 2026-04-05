# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
"""Slack connector."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from .base import (
    Connector,
    ConnectorRecord,
    ConnectorSyncCursor,
    ConnectorSyncPage,
    parse_datetime,
)


class SlackConnector(Connector):
    def __init__(
        self,
        token: str,
        *,
        channels: Sequence[str] | None = None,
        include_threads: bool = True,
        page_size: int = 100,
        client=None,
        base_url: str = "https://slack.com/api",
    ) -> None:
        super().__init__(page_size=page_size, client=client)
        self.token = token
        self.channels = list(channels or [])
        self.include_threads = include_threads
        self.base_url = base_url.rstrip("/")

    @property
    def source_name(self) -> str:
        return "slack"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8",
        }

    def authenticate(self) -> bool:
        return bool(self.token)

    def _message_record(
        self,
        channel_id: str,
        message: Mapping[str, Any],
        channel_name: str | None = None,
    ) -> ConnectorRecord:
        ts = str(message.get("ts") or "")
        user = str(message.get("user") or message.get("bot_id") or "unknown")
        text = str(message.get("text") or "")
        timestamp = parse_datetime(float(ts) if ts else None)
        return ConnectorRecord(
            source=self.source_name,
            id=f"{channel_id}:{ts}",
            title=channel_name or channel_id,
            content=f"[{user}] {text}".strip(),
            url=str(message.get("permalink") or ""),
            created_at=timestamp,
            updated_at=timestamp,
            metadata={
                "channel_id": channel_id,
                "channel_name": channel_name or channel_id,
                "user": user,
                "thread_ts": message.get("thread_ts"),
                "reply_count": message.get("reply_count", 0),
            },
        )

    def _channel_ids(self) -> list[str]:
        if self.channels:
            return list(self.channels)
        response = self._request_json(
            "GET",
            f"{self.base_url}/conversations.list",
            headers=self._headers,
            params={"limit": self.page_size},
        )
        return [channel["id"] for channel in response.get("channels", []) if channel.get("id")]

    def _channel_name_map(self) -> dict[str, str]:
        if self.channels:
            return {channel: channel for channel in self.channels}
        response = self._request_json(
            "GET",
            f"{self.base_url}/conversations.list",
            headers=self._headers,
            params={"limit": self.page_size},
        )
        return {
            channel["id"]: channel.get("name", channel["id"])
            for channel in response.get("channels", [])
            if channel.get("id")
        }

    def list_changes(
        self,
        *,
        cursor: ConnectorSyncCursor | None = None,
        limit: int | None = None,
    ) -> ConnectorSyncPage:
        limit = limit or self.page_size
        channel_names = self._channel_name_map()
        records: list[ConnectorRecord] = []
        channel_state = dict(cursor.state.get("channels", {})) if cursor else {}
        latest: datetime | None = cursor.updated_after if cursor else None
        for channel_id in self._channel_ids():
            oldest = channel_state.get(channel_id)
            params: dict[str, Any] = {"channel": channel_id, "limit": limit}
            if oldest:
                params["oldest"] = oldest
            elif cursor and cursor.updated_after:
                params["oldest"] = cursor.updated_after.timestamp()
            response = self._request_json(
                "GET",
                f"{self.base_url}/conversations.history",
                headers=self._headers,
                params=params,
            )
            messages = list(reversed(response.get("messages", [])))
            for message in messages:
                if len(records) >= limit:
                    break
                record = self._message_record(channel_id, message, channel_names.get(channel_id))
                records.append(record)
                ts = record.updated_at.timestamp() if record.updated_at else None
                if ts is not None:
                    channel_state[channel_id] = str(ts)
                latest = max(
                    [d for d in [latest, record.updated_at] if d is not None],
                    default=latest,
                )
                if self.include_threads and int(message.get("reply_count", 0) or 0) > 0:
                    replies = self._request_json(
                        "GET",
                        f"{self.base_url}/conversations.replies",
                        headers=self._headers,
                        params={"channel": channel_id, "ts": message.get("ts")},
                    )
                    for reply in replies.get("messages", [])[1:]:
                        reply_record = self._message_record(
                            channel_id, reply, channel_names.get(channel_id)
                        )
                        records.append(reply_record)
                        reply_ts = (
                            reply_record.updated_at.timestamp()
                            if reply_record.updated_at
                            else None
                        )
                        if reply_ts is not None:
                            channel_state[channel_id] = str(reply_ts)
                        latest = max(
                            [d for d in [latest, reply_record.updated_at] if d is not None],
                            default=latest,
                        )
                        if len(records) >= limit:
                            break
            if len(records) >= limit:
                break
        return ConnectorSyncPage(
            items=records,
            next_cursor=ConnectorSyncCursor(
                updated_after=latest, state={"channels": channel_state}
            ),
            has_more=len(records) >= limit,
            state={"channels": channel_state},
        )

    def fetch_item(self, item_id: str) -> ConnectorRecord | None:
        try:
            channel_id, ts = item_id.split(":", 1)
        except ValueError:
            return None
        response = self._request_json(
            "GET",
            f"{self.base_url}/conversations.history",
            headers=self._headers,
            params={"channel": channel_id, "latest": ts, "inclusive": True, "limit": 1},
        )
        messages = response.get("messages", [])
        if not messages:
            return None
        return self._message_record(channel_id, messages[0], channel_id)

    def search(self, query: str, *, limit: int = 100) -> list[ConnectorRecord]:
        response = self._request_json(
            "GET",
            f"{self.base_url}/search.messages",
            headers=self._headers,
            params={"query": query, "count": limit},
        )
        records: list[ConnectorRecord] = []
        for match in response.get("messages", {}).get("matches", []):
            channel = match.get("channel", {})
            channel_id = str(channel.get("id") or "")
            records.append(
                self._message_record(
                    channel_id, match, str(channel.get("name") or channel_id)
                )
            )
        return records
