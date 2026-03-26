# SPDX-License-Identifier: Apache-2.0
"""Tests for WooCommerce webhooks in the commerce module."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_brain.commerce.webhooks import (
    WOO_EVENT_ORDER_CREATED,
    WooCommerceEvent,
    WooCommerceEventDispatcher,
    WooCommerceWebhookHandler,
    register_commerce_webhooks,
)


def _sign(body: bytes, secret: str) -> str:
    """Helper to compute WooCommerce-style HMAC-SHA256 signatures."""

    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return base64.b64encode(mac.digest()).decode("utf-8")


class TestWooCommerceWebhookHandler:
    def test_verify_signature_valid(self) -> None:
        """Valid signature should verify successfully."""

        secret = "testsecret"
        body = b'{"id": 123}'
        sig = _sign(body, secret)

        handler = WooCommerceWebhookHandler(secret=secret)
        assert handler.verify_signature(body, sig) is True

    def test_verify_signature_invalid(self) -> None:
        """Invalid HMAC should fail verification."""

        secret = "testsecret"
        body = b'{"id": 123}'
        sig = _sign(body, "othersecret")

        handler = WooCommerceWebhookHandler(secret=secret)
        assert handler.verify_signature(body, sig) is False

    def test_parse_event_maps_topic(self) -> None:
        """Topics should be normalised and mapped to internal event types."""

        body = b'{"id": 1}'
        headers = {"X-WC-Webhook-Topic": "order.created"}

        handler = WooCommerceWebhookHandler(secret="ignored-for-parsing")
        event = handler.parse_event(body, headers)

        assert event.topic == "order.created"
        assert event.event_type == WOO_EVENT_ORDER_CREATED
        assert event.payload["id"] == 1


class TestWooCommerceEventDispatcher:
    def test_dispatch_uses_hooks_manager(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Dispatcher should forward events through HooksManager.fire."""

        recorded: dict[str, object] = {}

        def fake_fire(self, event_type: str, data: dict | None = None) -> None:  # type: ignore[override]
            recorded["event_type"] = event_type
            recorded["data"] = data or {}

        monkeypatch.setattr(
            "agentic_brain.commerce.webhooks.HooksManager.fire",
            fake_fire,
            raising=False,
        )

        dispatcher = WooCommerceEventDispatcher()
        event = WooCommerceEvent(
            topic="order.created",
            event_type=WOO_EVENT_ORDER_CREATED,
            payload={"id": 2},
            headers={"X-WC-Webhook-Topic": "order.created"},
        )

        dispatcher.dispatch(event)

        assert recorded["event_type"] == WOO_EVENT_ORDER_CREATED
        data = recorded["data"]
        assert isinstance(data, dict)
        assert data["payload"]["id"] == 2


class TestWooCommerceWebhookAPI:
    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch) -> TestClient:
        """Create a FastAPI app with commerce webhooks registered."""

        # Ensure a fresh handler is created with this secret
        from agentic_brain.commerce import webhooks as webhooks_module

        webhooks_module._handler = None  # type: ignore[attr-defined]

        monkeypatch.setenv("WOOCOMMERCE_WEBHOOK_SECRET", "testsecret")

        app = FastAPI()
        register_commerce_webhooks(app)
        return TestClient(app)

    def test_valid_webhook_returns_204_and_dispatches(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A valid signed webhook should be accepted and dispatched."""

        recorded: dict[str, object] = {}

        def fake_fire(self, event_type: str, data: dict | None = None) -> None:  # type: ignore[override]
            recorded["event_type"] = event_type
            recorded["data"] = data or {}

        monkeypatch.setattr(
            "agentic_brain.commerce.webhooks.HooksManager.fire",
            fake_fire,
            raising=False,
        )

        payload = {"id": 99}
        body_bytes = json.dumps(payload).encode("utf-8")
        sig = _sign(body_bytes, "testsecret")

        response = client.post(
            "/webhooks/woocommerce",
            data=body_bytes,
            headers={
                "Content-Type": "application/json",
                "X-WC-Webhook-Signature": sig,
                "X-WC-Webhook-Topic": "order.created",
            },
        )

        assert response.status_code == 204
        assert recorded["event_type"] == WOO_EVENT_ORDER_CREATED
        data = recorded["data"]
        assert isinstance(data, dict)
        assert data["payload"]["id"] == 99

    def test_missing_signature_rejected(self, client: TestClient) -> None:
        """Requests without signature header must be rejected."""

        response = client.post(
            "/webhooks/woocommerce",
            json={"id": 1},
            headers={"X-WC-Webhook-Topic": "order.created"},
        )

        assert response.status_code == 401

    def test_invalid_signature_rejected(self, client: TestClient) -> None:
        """Requests with invalid signature must be rejected."""

        response = client.post(
            "/webhooks/woocommerce",
            json={"id": 1},
            headers={
                "X-WC-Webhook-Topic": "order.created",
                "X-WC-Webhook-Signature": "invalid-signature",
            },
        )

        assert response.status_code == 401

    def test_missing_secret_returns_500(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If no secret is configured, the middleware should fail closed."""

        from agentic_brain.commerce import webhooks as webhooks_module

        # Reset cached handler and clear environment secrets
        webhooks_module._handler = None  # type: ignore[attr-defined]
        monkeypatch.delenv("WOOCOMMERCE_WEBHOOK_SECRET", raising=False)
        monkeypatch.delenv("COMMERCE_WOOCOMMERCE_WEBHOOK_SECRET", raising=False)

        app = FastAPI()
        register_commerce_webhooks(app)
        client = TestClient(app)

        response = client.post(
            "/webhooks/woocommerce",
            json={"id": 1},
            headers={
                "X-WC-Webhook-Topic": "order.created",
                "X-WC-Webhook-Signature": "any",
            },
        )

        assert response.status_code == 500
