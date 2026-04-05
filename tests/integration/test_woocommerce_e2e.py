# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors

"""End-to-end integration tests for WooCommerce commerce flows.

These tests run entirely locally:
- a mock WooCommerce REST API server simulates products and orders
- the real ``WooCommerceAgent`` talks to that server over HTTP
- the real webhook router verifies HMAC signatures via FastAPI ``TestClient``
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentic_brain.commerce import WooCommerceAgent, WooProduct
from agentic_brain.commerce import webhooks as webhook_module
from agentic_brain.commerce.webhooks import (
    WooCommerceWebhookHandler,
    register_commerce_webhooks,
)

pytestmark = pytest.mark.integration


def _deep_copy(value: Any) -> Any:
    """Return a JSON-safe deep copy for predictable server state mutation."""
    return json.loads(json.dumps(value))


@dataclass
class MockWooState:
    """In-memory state backing the mock WooCommerce API server."""

    expected_auth: str
    products: dict[int, dict[str, Any]] = field(default_factory=dict)
    orders: dict[int, dict[str, Any]] = field(default_factory=dict)
    next_product_id: int = 100
    next_order_id: int = 5000

    def seed_product(self, **overrides: Any) -> dict[str, Any]:
        product_id = overrides.pop("id", self.next_product_id)
        self.next_product_id = max(self.next_product_id, product_id + 1)
        regular_price = overrides.pop("regular_price", "0.00")
        payload = {
            "id": product_id,
            "name": overrides.pop("name", f"Product {product_id}"),
            "type": "simple",
            "regular_price": regular_price,
            "price": overrides.pop("price", regular_price),
            "description": overrides.pop("description", ""),
            "sku": overrides.pop("sku", f"SKU-{product_id}"),
            "stock": overrides.pop("stock", 0),
            "in_stock": overrides.pop("in_stock", True),
            "categories": overrides.pop("categories", []),
            "images": overrides.pop("images", []),
            "tags": overrides.pop("tags", []),
            "manage_stock": True,
        }
        payload.update(overrides)
        self.products[product_id] = payload
        return _deep_copy(payload)

    def create_product(self, payload: dict[str, Any]) -> dict[str, Any]:
        product = self.seed_product(**payload)
        if "price" not in payload:
            product["price"] = payload.get(
                "regular_price", product.get("price", "0.00")
            )
            self.products[product["id"]]["price"] = product["price"]
        return product

    def list_products(self, query: dict[str, list[str]]) -> list[dict[str, Any]]:
        products = list(self.products.values())
        search = (query.get("search") or [""])[0].strip().lower()
        sku = (query.get("sku") or [""])[0].strip().lower()
        if search:
            products = [
                product
                for product in products
                if search in product.get("name", "").lower()
                or search in product.get("description", "").lower()
                or search in product.get("sku", "").lower()
            ]
        if sku:
            products = [
                product for product in products if product.get("sku", "").lower() == sku
            ]
        return [
            _deep_copy(product)
            for product in sorted(products, key=lambda item: item["id"])
        ]

    def get_product(self, product_id: int) -> dict[str, Any] | None:
        product = self.products.get(product_id)
        return None if product is None else _deep_copy(product)

    def update_product(
        self, product_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        product = self.products.get(product_id)
        if product is None:
            return None
        product.update(payload)
        if "stock" in payload and "in_stock" not in payload:
            product["in_stock"] = payload["stock"] > 0
        if "regular_price" in payload and "price" not in payload:
            product["price"] = payload["regular_price"]
        return _deep_copy(product)

    def create_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        order_id = self.next_order_id
        self.next_order_id += 1
        status = payload.get("status", "pending")
        set_paid = payload.get("set_paid", False)
        if set_paid and status == "pending":
            status = "processing"
        order = {
            "id": order_id,
            "status": status,
            "customer_id": payload.get("customer_id", 0),
            "billing": payload.get("billing", {}),
            "shipping": payload.get("shipping", {}),
            "line_items": payload.get("line_items", []),
            "payment_method": payload.get("payment_method", "cod"),
            "payment_method_title": payload.get(
                "payment_method_title", "Cash on delivery"
            ),
            "set_paid": set_paid,
            "meta_data": payload.get("meta_data", []),
            "transaction_id": payload.get("transaction_id", ""),
            "status_history": [status],
        }
        self.orders[order_id] = order
        return _deep_copy(order)

    def get_order(self, order_id: int) -> dict[str, Any] | None:
        order = self.orders.get(order_id)
        return None if order is None else _deep_copy(order)

    def update_order(
        self, order_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        order = self.orders.get(order_id)
        if order is None:
            return None
        status = payload.get("status")
        if status and status != order.get("status"):
            order.setdefault("status_history", []).append(status)
        order.update(payload)
        return _deep_copy(order)


class MockWooHandler(BaseHTTPRequestHandler):
    """Minimal WooCommerce-like HTTP handler for integration testing."""

    server_version = "MockWooCommerce/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(
        self, format: str, *args: Any
    ) -> None:  # noqa: A003 - stdlib signature
        return None

    @property
    def state(self) -> MockWooState:
        return self.server.state  # type: ignore[attr-defined]

    def _json(self, status_code: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _unauthorized(self) -> None:
        self._json(401, {"message": "Unauthorized"})

    def _not_found(self) -> None:
        self._json(404, {"message": "Not found"})

    def _check_auth(self) -> bool:
        if self.headers.get("Authorization") != self.state.expected_auth:
            self._unauthorized()
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook
        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        query = parse_qs(parsed.query)

        if path == "/wp-json/wc/v3/products":
            self._json(200, self.state.list_products(query))
            return
        if path.startswith("/wp-json/wc/v3/products/"):
            product_id = int(path.rsplit("/", 1)[-1])
            product = self.state.get_product(product_id)
            if product is None:
                self._not_found()
                return
            self._json(200, product)
            return
        if path == "/wp-json/wc/v3/orders":
            self._json(200, [_deep_copy(order) for order in self.state.orders.values()])
            return
        if path.startswith("/wp-json/wc/v3/orders/"):
            order_id = int(path.rsplit("/", 1)[-1])
            order = self.state.get_order(order_id)
            if order is None:
                self._not_found()
                return
            self._json(200, order)
            return

        self._not_found()

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook
        if not self._check_auth():
            return

        path = urlparse(self.path).path.rstrip("/")
        payload = self._read_json()

        if path == "/wp-json/wc/v3/products":
            self._json(201, self.state.create_product(payload))
            return
        if path == "/wp-json/wc/v3/orders":
            self._json(201, self.state.create_order(payload))
            return

        self._not_found()

    def do_PUT(self) -> None:  # noqa: N802 - stdlib hook
        if not self._check_auth():
            return

        path = urlparse(self.path).path.rstrip("/")
        payload = self._read_json()

        if path.startswith("/wp-json/wc/v3/products/"):
            product_id = int(path.rsplit("/", 1)[-1])
            product = self.state.update_product(product_id, payload)
            if product is None:
                self._not_found()
                return
            self._json(200, product)
            return
        if path.startswith("/wp-json/wc/v3/orders/"):
            order_id = int(path.rsplit("/", 1)[-1])
            order = self.state.update_order(order_id, payload)
            if order is None:
                self._not_found()
                return
            self._json(200, order)
            return

        self._not_found()


class RecordingDispatcher:
    """Captures dispatched webhook events for assertions."""

    def __init__(self) -> None:
        self.events: list[Any] = []

    def dispatch(self, event: Any) -> None:
        self.events.append(event)


@pytest.fixture
def mock_woocommerce_server() -> tuple[str, MockWooState]:
    credentials = base64.b64encode(b"ck_test:cs_test").decode("ascii")
    state = MockWooState(expected_auth=f"Basic {credentials}")
    state.seed_product(
        id=101,
        name="Braille Keyboard",
        regular_price="199.95",
        price="199.95",
        description="Accessible mechanical keyboard",
        sku="BK-101",
        stock=6,
        in_stock=True,
        categories=[{"id": 1, "name": "Accessibility", "slug": "accessibility"}],
        images=[
            {
                "id": 10,
                "src": "https://example.test/images/braille-keyboard.jpg",
                "alt": "Braille keyboard with high-contrast keys",
            }
        ],
    )
    state.seed_product(
        id=102,
        name="VoiceOver Headphones",
        regular_price="89.00",
        price="89.00",
        description="Low-latency headset for screen-reader users",
        sku="VH-102",
        stock=12,
        in_stock=True,
        categories=[{"id": 2, "name": "Audio", "slug": "audio"}],
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockWooHandler)
    server.state = state  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.fixture
def woo_agent(mock_woocommerce_server: tuple[str, MockWooState]) -> WooCommerceAgent:
    base_url, _ = mock_woocommerce_server
    return WooCommerceAgent(
        url=base_url,
        consumer_key="ck_test",
        consumer_secret="cs_test",
        verify_ssl=False,
        timeout=5,
    )


@pytest.fixture
def webhook_client(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, RecordingDispatcher, str]:
    secret = "woo_test_secret"
    dispatcher = RecordingDispatcher()
    webhook_module._handler = WooCommerceWebhookHandler(
        secret=secret, dispatcher=dispatcher
    )
    monkeypatch.setenv("WOOCOMMERCE_WEBHOOK_SECRET", secret)

    app = FastAPI()
    register_commerce_webhooks(app)

    with TestClient(app) as client:
        yield client, dispatcher, secret

    webhook_module._handler = None


async def test_full_order_lifecycle_create_pay_ship_complete(
    woo_agent: WooCommerceAgent,
    mock_woocommerce_server: tuple[str, MockWooState],
) -> None:
    """Orders should move through the expected WooCommerce lifecycle states."""
    _, state = mock_woocommerce_server

    created = await woo_agent.create_order(
        {
            "payment_method": "stripe",
            "payment_method_title": "Stripe",
            "billing": {
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "AU",
            },
            "shipping": {
                "first_name": "Test",
                "last_name": "User",
                "address_1": "1 King William St",
                "city": "Adelaide",
                "postcode": "5000",
                "country": "AU",
            },
            "line_items": [{"product_id": 101, "quantity": 1, "price": "199.95"}],
        }
    )
    assert created["status"] == "pending"

    paid = await woo_agent.update_order(
        created["id"],
        {"status": "processing", "set_paid": True, "transaction_id": "pi_123456"},
    )
    shipped = await woo_agent.update_order(
        created["id"],
        {
            "status": "shipped",
            "meta_data": [{"key": "tracking_number", "value": "TRACK-123"}],
        },
    )
    completed = await woo_agent.update_order(
        created["id"],
        {"status": "completed", "date_completed": "2026-03-26T10:30:00Z"},
    )
    fetched = await woo_agent.get_order(created["id"])

    assert paid["status"] == "processing"
    assert shipped["status"] == "shipped"
    assert completed["status"] == "completed"
    assert fetched["transaction_id"] == "pi_123456"
    assert fetched["meta_data"][0]["value"] == "TRACK-123"
    assert state.orders[created["id"]]["status_history"] == [
        "pending",
        "processing",
        "shipped",
        "completed",
    ]


async def test_product_sync_fetches_searches_and_validates_catalog(
    woo_agent: WooCommerceAgent,
) -> None:
    """Product sync should return validated models and support search-based reconciliation."""
    created = await woo_agent.create_product(
        {
            "name": "Refreshable Braille Display",
            "regular_price": "1299.00",
            "price": "1299.00",
            "description": "Portable 20-cell braille display for screen-reader workflows",
            "sku": "BD-200",
            "stock": 4,
            "categories": [{"id": 3, "name": "Braille", "slug": "braille"}],
            "images": [
                {
                    "id": 22,
                    "src": "https://example.test/images/braille-display.jpg",
                    "alt": "Refreshable braille display on a laptop stand",
                }
            ],
        }
    )

    synced_products = await woo_agent.sync_products({"per_page": 50})
    braille_products = await woo_agent.search_products("braille")
    remote = await woo_agent.get_product(created["id"])

    assert any(isinstance(product, WooProduct) for product in synced_products)
    assert {product.sku for product in synced_products} >= {"BK-101", "BD-200"}
    assert [product["id"] for product in braille_products] == [101, created["id"]]
    assert remote["name"] == "Refreshable Braille Display"
    assert remote["categories"][0]["slug"] == "braille"


async def test_inventory_updates_adjust_stock_and_in_stock_flags(
    woo_agent: WooCommerceAgent,
) -> None:
    """Inventory updates should persist both quantity and availability state."""
    product = await woo_agent.create_product(
        {
            "name": "Accessible Smart Speaker",
            "regular_price": "249.00",
            "price": "249.00",
            "description": "Voice-first smart speaker with tactile controls",
            "sku": "SPK-001",
            "stock": 10,
            "in_stock": True,
            "categories": [{"id": 4, "name": "Smart Home", "slug": "smart-home"}],
        }
    )

    reduced = await woo_agent.update_inventory(product["id"], 3)
    depleted = await woo_agent.update_inventory(product["id"], 0)
    fetched = await woo_agent.get_product(product["id"])

    assert reduced["stock"] == 3
    assert reduced["in_stock"] is True
    assert depleted["stock"] == 0
    assert depleted["in_stock"] is False
    assert fetched["stock"] == 0
    assert fetched["manage_stock"] is True


def test_webhook_handling_accepts_valid_signed_payloads(
    webhook_client: tuple[TestClient, RecordingDispatcher, str],
) -> None:
    """Webhook endpoint should verify signatures and dispatch supported topics."""
    client, dispatcher, secret = webhook_client
    payload = {
        "id": 5001,
        "status": "processing",
        "billing": {"email": "joseph@example.com"},
    }
    body = json.dumps(payload).encode("utf-8")
    signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    ).decode("utf-8")

    response = client.post(
        "/webhooks/woocommerce",
        content=body,
        headers={
            "Content-Type": "application/json",
            "X-WC-Webhook-Topic": "order.updated",
            "X-WC-Webhook-Signature": signature,
        },
    )

    assert response.status_code == 204
    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert event.topic == "order.updated"
    assert event.payload["status"] == "processing"


def test_webhook_handling_rejects_invalid_signatures(
    webhook_client: tuple[TestClient, RecordingDispatcher, str],
) -> None:
    """Webhook endpoint should fail closed when the signature is invalid."""
    client, dispatcher, _ = webhook_client
    response = client.post(
        "/webhooks/woocommerce",
        json={"id": 1},
        headers={
            "X-WC-Webhook-Topic": "product.updated",
            "X-WC-Webhook-Signature": "invalid-signature",
        },
    )

    assert response.status_code == 401
    assert dispatcher.events == []
