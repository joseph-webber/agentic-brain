# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from agentic_brain import WooCommerceChatbot
from agentic_brain.commerce.chatbot import (
    ChatWidgetConfig,
    CommerceContext,
    CommerceIntent,
    CommerceIntentDetector,
    CommerceUserType,
    format_order_status,
    format_product_card,
    render_chat_widget_html,
    render_woocommerce_block,
    render_wordpress_shortcode,
)


class FakeWooAgent:
    def __init__(self) -> None:
        today = datetime.now(UTC).isoformat()
        yesterday = datetime(2026, 1, 1, tzinfo=UTC).isoformat()
        self.products = [
            {
                "id": 1,
                "name": "Blue Ocean Hoodie",
                "price": "49.00",
                "regular_price": "49.00",
                "stock_quantity": 3,
                "in_stock": True,
                "description": "Warm blue hoodie for cool nights.",
                "images": [
                    {"src": "https://example.com/hoodie.jpg", "alt": "Blue hoodie"}
                ],
                "attributes": [{"name": "Color", "options": ["Blue", "Black"]}],
            },
            {
                "id": 2,
                "name": "Travel Coffee Kit",
                "price": "29.00",
                "regular_price": "29.00",
                "stock_quantity": 12,
                "in_stock": True,
                "description": "Gift-ready coffee brewing set.",
            },
            {
                "id": 3,
                "name": "Premium Travel Mug",
                "price": "35.00",
                "regular_price": "35.00",
                "stock_quantity": 6,
                "in_stock": True,
                "description": "Insulated mug for daily commutes.",
            },
        ]
        self.orders = [
            {
                "id": 123,
                "status": "processing",
                "date_created": today,
                "currency": "USD",
                "total": "84.00",
                "customer_id": 99,
                "tracking_number": "TRACK123",
                "line_items": [
                    {
                        "id": 10,
                        "name": "Blue Ocean Hoodie",
                        "quantity": 1,
                        "total": "49.00",
                    },
                    {
                        "id": 11,
                        "name": "Travel Coffee Kit",
                        "quantity": 1,
                        "total": "29.00",
                    },
                ],
                "shipping_total": "5.00",
                "discount_total": "0.00",
                "total_tax": "1.00",
            },
            {
                "id": 124,
                "status": "completed",
                "date_created": yesterday,
                "currency": "USD",
                "total": "35.00",
                "customer_id": 99,
                "line_items": [
                    {
                        "id": 12,
                        "name": "Premium Travel Mug",
                        "quantity": 1,
                        "total": "35.00",
                    }
                ],
                "shipping_total": "0.00",
                "discount_total": "0.00",
                "total_tax": "0.00",
            },
        ]
        self.updated_products: list[tuple[int, dict[str, str]]] = []
        self.updated_orders: list[tuple[int, dict[str, str]]] = []

    async def get_products(self, params=None):
        return list(self.products)

    async def search_products(self, query: str):
        return [
            product
            for product in self.products
            if query.lower() in product["name"].lower()
        ]

    async def update_product(self, product_id: int, data: dict[str, str]):
        self.updated_products.append((product_id, data))
        product = next(
            product for product in self.products if product["id"] == product_id
        )
        product.update(data)
        return product

    async def get_orders(self, params=None):
        if params and params.get("customer") is not None:
            return [
                order
                for order in self.orders
                if order.get("customer_id") == params["customer"]
            ]
        return list(self.orders)

    async def get_order(self, order_id: int):
        return next(order for order in self.orders if order["id"] == order_id)

    async def update_order(self, order_id: int, data: dict[str, str]):
        self.updated_orders.append((order_id, data))
        order = next(order for order in self.orders if order["id"] == order_id)
        order.update(data)
        return order


def test_intent_detector_extracts_entities_for_guest_and_admin():
    detector = CommerceIntentDetector()
    guest_context = CommerceContext(user_type=CommerceUserType.GUEST)
    guest = detector.detect(
        'Compare "Blue Ocean Hoodie" and "Premium Travel Mug" under $50',
        user_type=CommerceUserType.GUEST,
        context=guest_context,
    )
    assert guest.intent is CommerceIntent.COMPARE_PRODUCTS
    assert guest.entities.product_names == ["Blue Ocean Hoodie", "Premium Travel Mug"]
    assert guest.entities.max_price == Decimal("50")

    admin = detector.detect(
        "Update product Blue Ocean Hoodie price to $99",
        user_type=CommerceUserType.ADMIN,
    )
    assert admin.intent is CommerceIntent.UPDATE_PRICE
    assert admin.entities.price == Decimal("99")
    assert "Blue Ocean Hoodie" in admin.entities.product_names


@pytest.mark.asyncio
async def test_admin_chatbot_handles_sales_stock_and_price_updates():
    chatbot = WooCommerceChatbot(FakeWooAgent(), store_name="Agentic Outfitters")

    sales = await chatbot.handle_message(
        "Show me today's sales", user_type=CommerceUserType.ADMIN
    )
    assert "Agentic Outfitters has 1 order" in sales.message
    assert sales.metadata["order_count"] == 1

    stock = await chatbot.handle_message(
        "What products are low on stock?",
        user_type=CommerceUserType.ADMIN,
    )
    assert "Blue Ocean Hoodie" in stock.message
    assert stock.cards[0]["stock_status"] == "In stock"

    price = await chatbot.handle_message(
        "Update product Blue Ocean Hoodie price to $99",
        user_type=CommerceUserType.ADMIN,
    )
    assert price.message == "Updated Blue Ocean Hoodie to $99.00."
    assert price.cards[0]["price"] == "$99.00"


@pytest.mark.asyncio
async def test_customer_chatbot_tracks_orders_history_and_recommendations():
    chatbot = WooCommerceChatbot(FakeWooAgent(), store_name="Agentic Outfitters")
    context = CommerceContext(user_type=CommerceUserType.CUSTOMER, customer_id=99)

    tracking = await chatbot.handle_message(
        "Where's my order #123?",
        user_type=CommerceUserType.CUSTOMER,
        context=context,
    )
    assert "order #123 is processing" in tracking.message.lower()
    assert tracking.cards[0]["tracking_number"] == "TRACK123"

    history = await chatbot.handle_message(
        "Show me my purchase history",
        user_type=CommerceUserType.CUSTOMER,
        context=context,
    )
    assert "I found 2 past orders" in history.message
    assert len(history.cards) == 2

    recommendations = await chatbot.handle_message(
        "Recommend products like my last purchase",
        user_type=CommerceUserType.CUSTOMER,
        context=context,
    )
    assert recommendations.cards
    assert any(card["title"] == "Premium Travel Mug" for card in recommendations.cards)


@pytest.mark.asyncio
async def test_guest_chatbot_handles_availability_gifts_comparisons_and_returns():
    chatbot = WooCommerceChatbot(FakeWooAgent(), store_name="Agentic Outfitters")

    availability = await chatbot.handle_message(
        "Do you have this in blue?",
        user_type=CommerceUserType.GUEST,
        context=CommerceContext(
            user_type=CommerceUserType.GUEST,
            last_product_names=["Blue Ocean Hoodie"],
        ),
    )
    assert "option" in availability.message.lower()
    assert availability.cards[0]["title"] == "Blue Ocean Hoodie"

    gifts = await chatbot.handle_message(
        "Help me find a gift under $50",
        user_type=CommerceUserType.GUEST,
    )
    assert "gift ideas under $50.00" in gifts.message.lower()
    assert len(gifts.cards) >= 2

    compare = await chatbot.handle_message(
        'Compare "Blue Ocean Hoodie" and "Premium Travel Mug"',
        user_type=CommerceUserType.GUEST,
    )
    assert "while Premium Travel Mug costs" in compare.message
    assert len(compare.cards) == 2

    returns = await chatbot.handle_message(
        "What's your return policy?",
        user_type=CommerceUserType.GUEST,
    )
    assert "Returns are accepted within 30 days" in returns.message


def test_formatters_and_widgets_are_accessible():
    product_card = format_product_card(
        {
            "id": 1,
            "name": "Blue Ocean Hoodie",
            "price": Decimal("49.00"),
            "currency": "USD",
            "stock": 3,
            "in_stock": True,
            "description": "Warm blue hoodie for cool nights.",
            "image": "https://example.com/hoodie.jpg",
        }
    )
    assert product_card["alt_text"] == "Product image for Blue Ocean Hoodie"

    order_card = format_order_status(
        {
            "id": 123,
            "status": "processing",
            "tracking_number": "TRACK123",
            "items": [{"name": "Blue Ocean Hoodie"}],
            "totals": {"total": Decimal("49.00"), "currency": "USD"},
        }
    )
    assert order_card["status"] == "Processing"

    widget_config = ChatWidgetConfig(
        api_endpoint="/api/chatbot", store_name="Agentic Outfitters"
    )
    html = render_chat_widget_html(widget_config)
    shortcode = render_wordpress_shortcode(widget_config)
    block = render_woocommerce_block(widget_config)
    assert 'aria-label="Open shopping assistant"' in html
    assert 'role="log"' in html
    assert "add_shortcode('agentic_brain_chatbot'" in shortcode
    assert "WooCommerce Chatbot" in block
