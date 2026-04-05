# SPDX-License-Identifier: Apache-2.0
"""WooCommerce webhook handling for agentic-brain commerce.

This module provides:

- :class:`WooCommerceWebhookHandler` for signature verification and payload parsing
- :class:`WooCommerceEventDispatcher` for forwarding events into the hooks system
- A FastAPI router exposing ``POST /webhooks/woocommerce`` with strict
  HMAC-SHA256 signature verification compatible with WooCommerce webhooks.

Security notes
--------------
- Webhooks are authenticated using ``X-WC-Webhook-Signature`` (base64-encoded
  HMAC-SHA256 of the raw request body).
- The shared secret is loaded from the
  ``WOOCOMMERCE_WEBHOOK_SECRET`` or ``COMMERCE_WOOCOMMERCE_WEBHOOK_SECRET``
  environment variables.
- Requests with missing/invalid signatures are rejected with HTTP 401.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from starlette.responses import Response as StarletteResponse
from starlette.types import ASGIApp

from agentic_brain.hooks import HooksManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event type constants (integrate with hooks/event system)
# ---------------------------------------------------------------------------

WOO_EVENT_ORDER_CREATED = "commerce.woocommerce.order.created"
WOO_EVENT_ORDER_UPDATED = "commerce.woocommerce.order.updated"
WOO_EVENT_PRODUCT_CREATED = "commerce.woocommerce.product.created"
WOO_EVENT_PRODUCT_UPDATED = "commerce.woocommerce.product.updated"
WOO_EVENT_CUSTOMER_CREATED = "commerce.woocommerce.customer.created"

# Mapping from WooCommerce webhook topic to internal event type
_TOPIC_TO_EVENT_TYPE: dict[str, str] = {
    "order.created": WOO_EVENT_ORDER_CREATED,
    "order.updated": WOO_EVENT_ORDER_UPDATED,
    "product.created": WOO_EVENT_PRODUCT_CREATED,
    "product.updated": WOO_EVENT_PRODUCT_UPDATED,
    "customer.created": WOO_EVENT_CUSTOMER_CREATED,
}


def _get_webhook_secret() -> str:
    """Return the WooCommerce webhook secret or raise if not configured.

    The secret is required for secure HMAC verification. Failing closed (500)
    when it is missing is safer than silently accepting unsigned webhooks.
    """

    secret = os.getenv("WOOCOMMERCE_WEBHOOK_SECRET") or os.getenv(
        "COMMERCE_WOOCOMMERCE_WEBHOOK_SECRET"
    )
    if not secret:
        raise ValueError("WooCommerce webhook secret is not configured")
    return secret


@dataclass
class WooCommerceEvent:
    """Structured representation of a WooCommerce webhook event."""

    topic: str
    event_type: Optional[str]
    payload: dict[str, Any]
    headers: dict[str, str]


class WooCommerceEventDispatcher:
    """Dispatch WooCommerce events into the agentic-brain hooks system.

    This provides a thin abstraction over :class:`HooksManager` so commerce
    events participate in the same event-driven architecture as chat, plugins
    and other subsystems.
    """

    def __init__(self, hooks_manager: Optional[HooksManager] = None) -> None:
        self._hooks = hooks_manager or HooksManager()

    def dispatch(self, event: WooCommerceEvent) -> None:
        """Dispatch a parsed WooCommerce event via :class:`HooksManager`.

        Unknown topics (not present in :data:`_TOPIC_TO_EVENT_TYPE`) are
        ignored but logged at debug level.
        """

        if not event.event_type:
            logger.debug(
                "Ignoring WooCommerce webhook with unsupported topic: %s", event.topic
            )
            return

        data = {
            "source": "woocommerce",
            "topic": event.topic,
            "payload": event.payload,
            "headers": {
                k: v for k, v in event.headers.items() if k.lower().startswith("x-wc-")
            },
        }

        logger.debug("Dispatching WooCommerce event: %s", event.event_type)
        self._hooks.fire(event.event_type, data)


class WooCommerceWebhookHandler:
    """Core logic for WooCommerce webhook handling.

    Responsibilities:
    - Verify webhook signatures using HMAC-SHA256
    - Parse JSON payloads
    - Normalise WooCommerce topics and dispatch supported events
    """

    def __init__(
        self,
        secret: Optional[str] = None,
        dispatcher: Optional[WooCommerceEventDispatcher] = None,
    ) -> None:
        self.secret = secret
        self.dispatcher = dispatcher or WooCommerceEventDispatcher()

    # ------------------------------------------------------------------
    # Signature verification
    # ------------------------------------------------------------------

    def verify_signature(
        self,
        body: bytes,
        signature: str,
        secret: Optional[str] = None,
    ) -> bool:
        """Verify WooCommerce HMAC-SHA256 signature.

        Args:
            body: Raw request body bytes (exact bytes used by WooCommerce).
            signature: Base64-encoded HMAC-SHA256 digest from
                ``X-WC-Webhook-Signature``.
            secret: Optional override secret; falls back to the instance
                secret and finally environment variables.

        Returns:
            True if the signature is valid, False otherwise.

        Raises:
            ValueError: If no secret is configured.
        """

        key = (secret or self.secret) or _get_webhook_secret()
        if not key:
            raise ValueError("WooCommerce webhook secret is not configured")

        mac = hmac.new(key.encode("utf-8"), body, hashlib.sha256)
        expected = base64.b64encode(mac.digest()).decode("utf-8")
        # Header access in Starlette/FastAPI is case-insensitive, but the
        # payload here should already be the header value.
        return hmac.compare_digest(expected, signature.strip())

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_topic(headers: Mapping[str, str]) -> str:
        """Extract the WooCommerce topic from headers.

        WooCommerce typically sends ``X-WC-Webhook-Topic`` such as
        ``order.created`` or ``product.updated``. As a fallback we combine
        ``X-WC-Webhook-Resource`` and ``X-WC-Webhook-Event``.
        """

        # Starlette's headers mapping is case-insensitive.
        topic = headers.get("X-WC-Webhook-Topic")
        if topic:
            return topic

        resource = headers.get("X-WC-Webhook-Resource")
        event = headers.get("X-WC-Webhook-Event")
        if resource and event:
            return f"{resource}.{event}"

        raise ValueError("Missing WooCommerce webhook topic headers")

    @staticmethod
    def _parse_json(body: bytes) -> dict[str, Any]:
        try:
            # WooCommerce sends JSON payloads by default
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON payload: {exc}") from exc

    def parse_event(self, body: bytes, headers: Mapping[str, str]) -> WooCommerceEvent:
        """Parse raw body + headers into :class:`WooCommerceEvent`."""

        topic = self._get_topic(headers)
        payload = self._parse_json(body)
        event_type = _TOPIC_TO_EVENT_TYPE.get(topic)
        return WooCommerceEvent(
            topic=topic,
            event_type=event_type,
            payload=payload,
            headers=dict(headers),
        )

    # ------------------------------------------------------------------
    # High-level processing
    # ------------------------------------------------------------------

    def handle(self, body: bytes, headers: Mapping[str, str]) -> WooCommerceEvent:
        """Parse and dispatch a WooCommerce webhook.

        The signature should already be verified by middleware before this
        method is invoked.
        """

        event = self.parse_event(body, headers)
        self.dispatcher.dispatch(event)
        return event


# ---------------------------------------------------------------------------
# FastAPI integration
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/webhooks", tags=["commerce", "webhooks"])

# Single shared handler/dispatcher used by the router and middleware
_handler: Optional[WooCommerceWebhookHandler] = None


def get_woocommerce_handler() -> WooCommerceWebhookHandler:
    """Return a process-wide WooCommerce handler instance."""

    global _handler
    if _handler is None:
        try:
            secret = _get_webhook_secret()
        except ValueError:
            # Defer missing-secret error until first request so tests can
            # configure environment dynamically.
            secret = None
        _handler = WooCommerceWebhookHandler(secret=secret)
    return _handler


class WooCommerceSignatureMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces WooCommerce HMAC signature verification.

    This middleware only intercepts ``POST /webhooks/woocommerce`` requests
    and fails fast with 401/500 responses when verification fails.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._handler = get_woocommerce_handler()

    async def dispatch(
        self, request: StarletteRequest, call_next
    ) -> StarletteResponse:  # type: ignore[override]
        # Only protect the WooCommerce webhook endpoint
        if (
            request.method.upper() == "POST"
            and request.url.path == "/webhooks/woocommerce"
        ):
            signature = request.headers.get("X-WC-Webhook-Signature")
            if not signature:
                logger.warning("Missing WooCommerce webhook signature header")
                return StarletteResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content="Missing WooCommerce webhook signature",
                    media_type="text/plain",
                )

            body = await request.body()
            try:
                if not self._handler.verify_signature(body, signature):
                    logger.warning("Invalid WooCommerce webhook signature")
                    return StarletteResponse(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        content="Invalid WooCommerce webhook signature",
                        media_type="text/plain",
                    )
            except ValueError as exc:
                logger.error("WooCommerce webhook secret not configured: %s", exc)
                return StarletteResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content="WooCommerce webhook secret not configured",
                    media_type="text/plain",
                )

            # Ensure downstream handlers can read the body again
            request._body = body  # type: ignore[attr-defined]

        return await call_next(request)


@router.post(
    "/woocommerce",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="WooCommerce webhook endpoint",
    description=(
        "Secure WooCommerce webhook receiver with HMAC-SHA256 signature "
        "verification and dispatch into the agentic-brain hooks system."
    ),
)
async def woocommerce_webhook(request: Request) -> Response:
    """Receive a WooCommerce webhook and dispatch it into the event system.

    Signature verification is handled by :class:`WooCommerceSignatureMiddleware`.
    """

    body = await request.body()
    handler = get_woocommerce_handler()

    try:
        event = handler.handle(body, request.headers)
    except ValueError as exc:
        # Malformed webhook topics or payloads are considered client errors.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    logger.info(
        "Processed WooCommerce webhook: topic=%s, event_type=%s",
        event.topic,
        event.event_type,
    )
    # 204 No Content is standard for webhook receivers
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def register_commerce_webhooks(app) -> None:
    """Register WooCommerce webhook routes and middleware with a FastAPI app."""

    # Add signature verification middleware just once
    app.add_middleware(WooCommerceSignatureMiddleware)
    app.include_router(router)
