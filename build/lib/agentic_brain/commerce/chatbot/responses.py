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

"""Response builders and formatters for the WooCommerce chatbot."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


def format_currency(
    value: Decimal | int | float | str | None,
    currency: str = "USD",
) -> str:
    """Format a money value for display."""
    if value is None:
        return f"{currency} 0.00"
    amount = Decimal(str(value))
    symbol = (
        "$"
        if currency.upper() in {"USD", "AUD", "CAD", "NZD"}
        else f"{currency.upper()} "
    )
    return f"{symbol}{amount.quantize(Decimal('0.01'))}"


def format_product_card(
    product: dict[str, Any], currency: str = "USD"
) -> dict[str, Any]:
    """Create a structured product card for web or chat rendering."""
    stock = int(product.get("stock", 0) or 0)
    in_stock = bool(product.get("in_stock", stock > 0))
    description = str(product.get("description", "")).strip()
    return {
        "type": "product",
        "id": product.get("id"),
        "title": product.get("name", "Unnamed product"),
        "price": format_currency(
            product.get("price", 0), product.get("currency", currency)
        ),
        "sku": product.get("sku"),
        "stock_status": "In stock" if in_stock else "Out of stock",
        "stock": stock,
        "summary": (
            description[:180] + ("…" if len(description) > 180 else "")
            if description
            else ""
        ),
        "image": product.get("image") or product.get("image_url"),
        "url": product.get("permalink") or product.get("url"),
        "alt_text": product.get("alt_text")
        or f"Product image for {product.get('name', 'product')}",
    }


def format_order_status(order: dict[str, Any]) -> dict[str, Any]:
    """Build an order status payload suitable for chat UIs."""
    totals = order.get("totals", {})
    return {
        "type": "order_status",
        "order_id": order.get("id"),
        "status": str(order.get("status", "unknown")).replace("_", " ").title(),
        "tracking_number": order.get("tracking_number"),
        "fulfilment_summary": order.get("fulfilment_summary")
        or order.get("customer_note")
        or "",
        "total": format_currency(
            totals.get("total", order.get("total", 0)),
            totals.get("currency", order.get("currency", "USD")),
        ),
        "items": [item.get("name", "Item") for item in order.get("items", [])],
    }


class ResponseTemplates:
    """High-level response templates used by the WooCommerce chatbot."""

    @staticmethod
    def admin_sales(
        store_name: str,
        *,
        order_count: int,
        total_sales: Decimal,
        average_order_value: Decimal,
        currency: str,
    ) -> str:
        return (
            f"{store_name} has {order_count} order{'s' if order_count != 1 else ''} today, "
            f"bringing in {format_currency(total_sales, currency)}. "
            f"Average order value is {format_currency(average_order_value, currency)}."
        )

    @staticmethod
    def low_stock(store_name: str, products: list[dict[str, Any]]) -> str:
        if not products:
            return f"Good news — {store_name} has no products below the low-stock threshold right now."
        names = ", ".join(
            f"{product['name']} ({product['stock']} left)" for product in products[:5]
        )
        return f"These products need attention: {names}."

    @staticmethod
    def refund_processed(order_id: int, status: str) -> str:
        return f"Refund workflow started for order #{order_id}. Current order status: {status}."

    @staticmethod
    def price_updated(product_name: str, price: Decimal, currency: str) -> str:
        return f"Updated {product_name} to {format_currency(price, currency)}."

    @staticmethod
    def order_status(order_card: dict[str, Any]) -> str:
        items = ", ".join(order_card.get("items") or ["your items"])
        detail = (
            f" Tracking number: {order_card['tracking_number']}."
            if order_card.get("tracking_number")
            else ""
        )
        return (
            f"Order #{order_card['order_id']} is {order_card['status'].lower()} for {items}. "
            f"Order total is {order_card['total']}.{detail}"
        )

    @staticmethod
    def return_guidance(policy: str, order_id: int | None = None) -> str:
        prefix = f"For order #{order_id}, " if order_id is not None else ""
        return f"{prefix}here's the return guidance: {policy}"

    @staticmethod
    def purchase_history(order_count: int, total_spend: Decimal, currency: str) -> str:
        return (
            f"I found {order_count} past order{'s' if order_count != 1 else ''} with total spend of "
            f"{format_currency(total_spend, currency)}."
        )

    @staticmethod
    def recommendations(products: list[dict[str, Any]]) -> str:
        if not products:
            return "I couldn't find closely related products yet, but I can keep browsing with you."
        names = ", ".join(product.get("name", "Product") for product in products[:3])
        return f"You might also like {names}."

    @staticmethod
    def availability(products: list[dict[str, Any]], color: str | None = None) -> str:
        if not products:
            if color:
                return f"I couldn't find a matching product in {color}."
            return "I couldn't find a matching product right now."
        if color:
            return f"I found {len(products)} option{'s' if len(products) != 1 else ''} in {color}."
        return f"I found {len(products)} matching product{'s' if len(products) != 1 else ''}."

    @staticmethod
    def gift_guide(
        products: list[dict[str, Any]], budget: Decimal, currency: str
    ) -> str:
        if not products:
            return f"I couldn't find a gift under {format_currency(budget, currency)} just yet."
        names = ", ".join(product.get("name", "Product") for product in products[:3])
        return (
            f"Here are gift ideas under {format_currency(budget, currency)}: {names}."
        )

    @staticmethod
    def comparison(left: dict[str, Any], right: dict[str, Any], currency: str) -> str:
        return (
            f"{left['name']} costs {format_currency(left['price'], currency)} with stock {left['stock']}, while "
            f"{right['name']} costs {format_currency(right['price'], currency)} with stock {right['stock']}."
        )

    @staticmethod
    def fallback(user_type: str) -> str:
        audience = {
            "admin": "manage your store",
            "customer": "help with your account and orders",
            "guest": "help you shop",
        }.get(user_type, "help")
        return f"I can {audience}. Try asking about orders, products, returns, or recommendations."


__all__ = [
    "ResponseTemplates",
    "format_currency",
    "format_order_status",
    "format_product_card",
]
