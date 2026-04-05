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

"""Durable WooCommerce webhook ingestion and processing.

The existing :mod:`agentic_brain.commerce.webhooks` module provides a secure
FastAPI endpoint plus signature verification and dispatch. This module adds the
missing durability layer for real-world webhook delivery:

- Idempotent processing (at-least-once deliveries become effectively exactly-once)
- Retry with exponential backoff
- Dead letter queue for poisoned events
- Event-sourced logging to the durability event store

Design
------
WooCommerce webhooks are delivered at least once; duplicates and retries are
expected. To make processing idempotent across workers, each delivery is treated
as a small durable "workflow" using :class:`agentic_brain.durability.event_store.EventStore`.

If Redpanda / aiokafka is unavailable, the event store falls back to an
in-memory implementation (useful for tests and local development).
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from agentic_brain.commerce.webhooks import WooCommerceEvent, WooCommerceWebhookHandler
from agentic_brain.durability.event_store import EventStore, get_event_store
from agentic_brain.durability.events import (
    EventType,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
)
from agentic_brain.durability.retry import API_RETRY_POLICY, RetryPolicy, with_retry
from agentic_brain.durability.task_queue import Task, TaskPriority, TaskQueue
from agentic_brain.hooks import HooksManager

logger = logging.getLogger(__name__)

WEBHOOK_TASK_TYPE = "commerce.woocommerce.webhook"


class WebhookVerificationError(ValueError):
    """Raised when a webhook cannot be verified."""


class WebhookDuplicateError(RuntimeError):
    """Raised when a webhook delivery has already been processed."""


@dataclass(frozen=True, slots=True)
class WebhookEnvelope:
    """Durable representation of an inbound webhook."""

    delivery_id: str
    topic: str
    headers: dict[str, str]
    body: bytes
    received_at: datetime

    @property
    def body_hash(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


def _normalize_headers(headers: Mapping[str, Any]) -> dict[str, str]:
    return {str(k): str(v) for k, v in headers.items()}


def _delivery_id(body: bytes, headers: Mapping[str, Any]) -> str:
    """Return a stable idempotency key for the webhook delivery."""

    for key in (
        "X-WC-Webhook-Delivery-ID",
        "X-WC-Webhook-Delivery-Id",
        "X-WC-Webhook-Event-Id",
    ):
        value = headers.get(key)
        if value:
            return str(value)

    topic = str(headers.get("X-WC-Webhook-Topic", ""))
    digest = hashlib.sha256(topic.encode("utf-8") + b"|" + body).hexdigest()
    return digest[:24]


def _workflow_id(delivery_id: str) -> str:
    return f"woocommerce-webhook:{delivery_id}"


class DurableWooCommerceWebhookService:
    """Durable webhook ingestion + background processing via TaskQueue."""

    def __init__(
        self,
        *,
        secret: str,
        hooks: HooksManager | None = None,
        event_store: EventStore | None = None,
        queue: TaskQueue | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        self._handler = WooCommerceWebhookHandler(secret=secret)
        self._hooks = hooks or HooksManager()
        self._event_store = event_store or get_event_store()
        self._queue = queue or TaskQueue("commerce-woocommerce-webhooks")
        self._retry_policy = retry_policy or API_RETRY_POLICY
        self._connected = False

    async def connect(self) -> None:
        if self._connected:
            return
        await self._queue.connect()
        await self._event_store.connect()
        self._connected = True

    async def already_processed(self, delivery_id: str) -> bool:
        """Return True if the delivery has a terminal completion event."""

        events = await self._event_store.load_events(_workflow_id(delivery_id))
        return any(
            event.event_type
            in (EventType.WORKFLOW_COMPLETED, EventType.WORKFLOW_FAILED)
            for event in events
        )

    async def ingest(self, body: bytes, headers: Mapping[str, Any]) -> WebhookEnvelope:
        """Verify, log, and enqueue an inbound webhook."""

        headers_dict = _normalize_headers(headers)
        signature = headers_dict.get("X-WC-Webhook-Signature")
        if not signature:
            raise WebhookVerificationError("missing X-WC-Webhook-Signature header")

        if not self._handler.verify_signature(body, signature):
            raise WebhookVerificationError("invalid webhook signature")

        delivery_id = _delivery_id(body, headers_dict)
        if await self.already_processed(delivery_id):
            raise WebhookDuplicateError(
                f"webhook delivery already processed: {delivery_id}"
            )

        envelope = WebhookEnvelope(
            delivery_id=delivery_id,
            topic=str(headers_dict.get("X-WC-Webhook-Topic", "")),
            headers={
                k: v for k, v in headers_dict.items() if k.lower().startswith("x-wc-")
            },
            body=body,
            received_at=datetime.now(UTC),
        )

        await self._event_store.publish(
            WorkflowStarted(
                workflow_id=_workflow_id(delivery_id),
                workflow_type="woocommerce_webhook",
                args={
                    "delivery_id": delivery_id,
                    "topic": envelope.topic,
                    "body_hash": envelope.body_hash,
                },
                task_queue=self._queue.queue_name,
            )
        )

        await self._queue.enqueue(
            WEBHOOK_TASK_TYPE,
            {
                "delivery_id": envelope.delivery_id,
                "topic": envelope.topic,
                "headers": envelope.headers,
                "body": envelope.body.decode("utf-8"),
            },
            priority=TaskPriority.NORMAL,
            workflow_id=_workflow_id(delivery_id),
            max_attempts=self._retry_policy.max_attempts,
        )

        logger.info(
            "Queued WooCommerce webhook delivery_id=%s topic=%s",
            envelope.delivery_id,
            envelope.topic,
        )

        return envelope

    async def process_task(self, task: Task) -> WooCommerceEvent:
        """Process a single webhook task (idempotent & event-sourced)."""

        payload = task.payload
        delivery_id = str(payload.get("delivery_id") or "")
        workflow_id = task.workflow_id or _workflow_id(delivery_id)

        body_raw = str(payload.get("body") or "").encode("utf-8")
        headers = _normalize_headers(payload.get("headers") or {})

        @with_retry(self._retry_policy)
        def _dispatch() -> WooCommerceEvent:
            event = self._handler.handle(body_raw, headers)
            data = {
                "source": "woocommerce",
                "topic": event.topic,
                "payload": event.payload,
                "headers": event.headers,
            }
            if event.event_type:
                self._hooks.fire(event.event_type, data)
            return event

        try:
            event = _dispatch()
            await self._event_store.publish(
                WorkflowCompleted(
                    workflow_id=workflow_id,
                    result={
                        "delivery_id": delivery_id,
                        "topic": event.topic,
                        "event_type": event.event_type,
                    },
                )
            )
            await self._queue.acknowledge(task.task_id, result={"status": "ok"})
            return event
        except Exception as exc:
            await self._event_store.publish(
                WorkflowFailed(
                    workflow_id=workflow_id,
                    error=str(exc),
                    error_type=exc.__class__.__name__,
                    retryable=True,
                )
            )
            await self._queue.fail(task.task_id, error=str(exc), retry=True)
            raise

    async def work_once(
        self, *, worker_id: str = "woo-webhooks", timeout: float = 1.0
    ) -> int:
        """Poll and process up to one webhook task. Returns number processed."""

        tasks = await self._queue.poll(
            worker_id=worker_id, max_tasks=1, timeout=timeout
        )
        if not tasks:
            return 0
        await self.process_task(tasks[0])
        return 1


def loads_envelope_from_task(task: Task) -> WebhookEnvelope:
    """Utility for inspecting queued tasks in monitoring/ops tools."""

    payload = task.payload
    body = str(payload.get("body") or "").encode("utf-8")
    headers = _normalize_headers(payload.get("headers") or {})
    return WebhookEnvelope(
        delivery_id=str(payload.get("delivery_id") or task.task_id),
        topic=str(payload.get("topic") or headers.get("X-WC-Webhook-Topic") or ""),
        headers=headers,
        body=body,
        received_at=(
            datetime.fromisoformat(payload.get("received_at"))
            if payload.get("received_at")
            else datetime.now(UTC)
        ),
    )
