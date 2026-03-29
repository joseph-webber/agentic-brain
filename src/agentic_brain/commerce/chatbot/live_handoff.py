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
"""Live hand-off helpers for escalating from bot to human support."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, Iterable, List, Mapping, Optional


@dataclass(frozen=True)
class HandoffRequest:
    """Represents a request to escalate a chat to a human agent."""

    channel: str
    reason: str
    priority: str
    summary: str
    queue_token: str


@dataclass(frozen=True)
class QueueStatus:
    """Simple queue status for updating the customer."""

    position: int
    estimated_wait_minutes: int


@dataclass(frozen=True)
class CallbackRequest:
    """Represents a scheduled callback request."""

    contact_method: str
    window_start: datetime
    window_end: datetime
    confirmed: bool


class LiveHandoffAssistant:
    """Pure helper for human hand-off flows.

    This class does not own any queues; instead it calculates
    deterministic values that can be turned into user-facing updates
    and payloads for the actual support tooling.
    """

    def build_handoff_request(
        self,
        *,
        conversation: Iterable[Mapping[str, Any]],
        reason: str,
        channel: str = "chat",
    ) -> HandoffRequest:
        """Create a hand-off request from conversation history."""

        messages = list(conversation)
        last_user_text = ""
        for msg in reversed(messages):
            role = str(msg.get("role", "")).lower()
            if role == "user":
                last_user_text = str(msg.get("content", ""))
                break

        if last_user_text:
            summary = f"Customer said: {last_user_text[:200]}"
        else:
            summary = "Customer requested hand-off to a human."

        reason_lower = reason.lower()
        priority = "normal"
        if any(word in reason_lower for word in ["angry", "upset", "urgent", "refund"]):
            priority = "high"

        queue_token = f"{int(datetime.now(UTC).timestamp())}-{hash(summary) & 0xFFFF:x}"

        return HandoffRequest(
            channel=channel,
            reason=reason,
            priority=priority,
            summary=summary,
            queue_token=queue_token,
        )

    def build_context_payload(
        self,
        *,
        customer: Mapping[str, Any] | None = None,
        cart: Mapping[str, Any] | None = None,
        order: Mapping[str, Any] | None = None,
        conversation: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Combine structured context into a payload for a support agent."""

        payload: dict[str, Any] = {
            "customer": dict(customer) if customer is not None else None,
            "cart": dict(cart) if cart is not None else None,
            "order": dict(order) if order is not None else None,
        }
        if conversation is not None:
            # Truncate very long histories – the full log can live elsewhere.
            convo_list = list(conversation)[-50:]
            payload["conversation_preview"] = [
                {"role": m.get("role", ""), "content": m.get("content", "")[:500]}
                for m in convo_list
            ]
        return payload

    def queue_status(
        self,
        *,
        position: int,
        total_ahead: Optional[int] = None,
        average_handle_minutes: int = 5,
    ) -> QueueStatus:
        """Return a :class:`QueueStatus` with deterministic wait time."""

        if position < 1:
            position = 1
        ahead = total_ahead if total_ahead is not None else max(position - 1, 0)
        wait = max(ahead, 0) * max(average_handle_minutes, 1)
        return QueueStatus(position=position, estimated_wait_minutes=wait)

    def schedule_callback(
        self,
        *,
        contact_method: str,
        window_start: datetime,
        window_end: datetime,
    ) -> CallbackRequest:
        """Create a :class:`CallbackRequest` with basic validation."""

        if window_end <= window_start:
            # Normalise to a 30 minute window from start
            window_end = window_start + timedelta(minutes=30)

        now = datetime.now(UTC)
        confirmed = window_start >= now

        return CallbackRequest(
            contact_method=contact_method,
            window_start=window_start,
            window_end=window_end,
            confirmed=confirmed,
        )
