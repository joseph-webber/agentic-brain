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
"""Multi-channel abstractions for enterprise commerce support."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timezone
from typing import Mapping


@dataclass(frozen=True)
class ChannelCapabilities:
    rich_media: bool
    supports_templates: bool
    supports_read_receipts: bool
    max_message_length: int


@dataclass(frozen=True)
class ChannelMessage:
    channel: str
    external_id: str
    customer_id: str
    text: str
    timestamp: datetime
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class UnifiedInboxItem:
    channel: str
    conversation_id: str
    latest_message: str
    unread_count: int
    priority: str
    customer_id: str
    last_updated: datetime


class BaseChannelAdapter:
    channel_name = "base"
    capabilities = ChannelCapabilities(False, False, False, 1000)

    def normalize_inbound(self, payload: Mapping[str, object]) -> ChannelMessage:
        timestamp = payload.get("timestamp")
        if not isinstance(timestamp, datetime):
            timestamp = datetime.now(UTC)
        return ChannelMessage(
            channel=self.channel_name,
            external_id=str(payload.get("id", "")),
            customer_id=str(payload.get("customer_id", payload.get("from", "unknown"))),
            text=str(payload.get("text", payload.get("message", ""))),
            timestamp=timestamp,
            metadata=dict(payload),
        )

    def prepare_outbound(self, customer_id: str, text: str) -> dict[str, object]:
        return {
            "channel": self.channel_name,
            "to": customer_id,
            "message": text[: self.capabilities.max_message_length],
        }


class WhatsAppAdapter(BaseChannelAdapter):
    channel_name = "whatsapp"
    capabilities = ChannelCapabilities(True, True, True, 4096)


class FacebookMessengerAdapter(BaseChannelAdapter):
    channel_name = "facebook_messenger"
    capabilities = ChannelCapabilities(True, True, True, 2000)


class InstagramDMAdapter(BaseChannelAdapter):
    channel_name = "instagram_dm"
    capabilities = ChannelCapabilities(True, False, True, 1000)


class SMSAdapter(BaseChannelAdapter):
    channel_name = "sms"
    capabilities = ChannelCapabilities(False, False, False, 160)


class UnifiedInbox:
    """Aggregate channel messages into a single support inbox."""

    def __init__(self) -> None:
        self._messages: list[ChannelMessage] = []

    def ingest(
        self, adapter: BaseChannelAdapter, payload: Mapping[str, object]
    ) -> ChannelMessage:
        message = adapter.normalize_inbound(payload)
        self._messages.append(message)
        return message

    def list_items(self) -> list[UnifiedInboxItem]:
        grouped: dict[tuple[str, str], list[ChannelMessage]] = {}
        for message in self._messages:
            key = (message.channel, message.customer_id)
            grouped.setdefault(key, []).append(message)

        items: list[UnifiedInboxItem] = []
        for (channel, customer_id), messages in grouped.items():
            ordered = sorted(messages, key=lambda msg: msg.timestamp)
            latest = ordered[-1]
            unread = sum(1 for msg in ordered if not msg.metadata.get("read", False))
            priority = (
                "high"
                if any(msg.metadata.get("urgent") for msg in ordered)
                else "normal"
            )
            items.append(
                UnifiedInboxItem(
                    channel=channel,
                    conversation_id=f"{channel}:{customer_id}",
                    latest_message=latest.text,
                    unread_count=unread,
                    priority=priority,
                    customer_id=customer_id,
                    last_updated=latest.timestamp,
                )
            )

        items.sort(
            key=lambda item: (item.priority != "high", -item.last_updated.timestamp())
        )
        return items

    def conversation_thread(
        self, channel: str, customer_id: str
    ) -> list[ChannelMessage]:
        return sorted(
            [
                message
                for message in self._messages
                if message.channel == channel and message.customer_id == customer_id
            ],
            key=lambda msg: msg.timestamp,
        )


__all__ = [
    "BaseChannelAdapter",
    "ChannelCapabilities",
    "ChannelMessage",
    "FacebookMessengerAdapter",
    "InstagramDMAdapter",
    "SMSAdapter",
    "UnifiedInbox",
    "UnifiedInboxItem",
    "WhatsAppAdapter",
]
