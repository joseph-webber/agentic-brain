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

"""WooCommerce chatbot orchestration for admin, customer, and guest journeys."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .intents import (
    CommerceContext,
    CommerceIntent,
    CommerceIntentDetector,
    CommerceUserType,
    IntentMatch,
)
from .responses import ResponseTemplates, format_order_status, format_product_card


@dataclass(slots=True)
class ChatbotReply:
    """Structured chatbot output for API, UI, or test consumers."""

    message: str
    intent: IntentMatch
    context: CommerceContext
    cards: list[dict[str, Any]] = field(default_factory=list)
    actions: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class WooCommerceChatbot:
    """Natural-language storefront assistant built on top of WooCommerce data."""

    def __init__(
        self,
        woo_agent: Any | None = None,
        *,
        store_name: str = "Your WooCommerce Store",
        default_currency: str = "USD",
        intent_detector: CommerceIntentDetector | None = None,
        low_stock_threshold: int = 5,
        policy_provider: Any | None = None,
    ) -> None:
        self.woo_agent = woo_agent
        self.store_name = store_name
        self.default_currency = default_currency
        self.intent_detector = intent_detector or CommerceIntentDetector()
        self.low_stock_threshold = low_stock_threshold
        self.policy_provider = policy_provider or self._default_policy_provider

    async def handle_message(
        self,
        message: str,
        *,
        user_type: CommerceUserType,
        context: CommerceContext | None = None,
        customer_id: int | None = None,
        customer_email: str | None = None,
    ) -> ChatbotReply:
        """Process a storefront message and return a structured chatbot reply."""
        context = context or CommerceContext(user_type=user_type)
        if customer_id is not None:
            context.customer_id = customer_id
        if customer_email is not None:
            context.customer_email = customer_email

        intent = self.intent_detector.detect(
            message, user_type=user_type, context=context
        )
        entities = intent.entities
        if entities.order_ids:
            context.last_order_id = entities.order_ids[0]
        if entities.product_names:
            context.remember_products(entities.product_names)
            context.remember_browse(entities.product_names)
        context.last_intent = intent.intent

        handler = {
            CommerceIntent.SHOW_SALES: self._handle_show_sales,
            CommerceIntent.LOW_STOCK: self._handle_low_stock,
            CommerceIntent.PROCESS_REFUND: self._handle_refund,
            CommerceIntent.UPDATE_PRICE: self._handle_update_price,
            CommerceIntent.TRACK_ORDER: self._handle_track_order,
            CommerceIntent.RETURN_ITEM: self._handle_return_item,
            CommerceIntent.PURCHASE_HISTORY: self._handle_purchase_history,
            CommerceIntent.RECOMMEND_PRODUCTS: self._handle_recommend_products,
            CommerceIntent.PRODUCT_AVAILABILITY: self._handle_product_availability,
            CommerceIntent.RETURN_POLICY: self._handle_return_policy,
            CommerceIntent.GIFT_SEARCH: self._handle_gift_search,
            CommerceIntent.COMPARE_PRODUCTS: self._handle_compare_products,
            CommerceIntent.FALLBACK: self._handle_fallback,
        }[intent.intent]
        return await handler(intent, context)

    def handle_message_sync(
        self,
        message: str,
        *,
        user_type: CommerceUserType,
        context: CommerceContext | None = None,
        customer_id: int | None = None,
        customer_email: str | None = None,
    ) -> ChatbotReply:
        """Synchronous convenience wrapper for web frameworks without async routes."""
        return asyncio.run(
            self.handle_message(
                message,
                user_type=user_type,
                context=context,
                customer_id=customer_id,
                customer_email=customer_email,
            )
        )

    async def _handle_show_sales(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        orders = await self._get_orders()
        today = datetime.now(UTC).date()
        todays_orders = [
            order for order in orders if self._order_date(order).date() == today
        ]
        total_sales = sum(
            (Decimal(str(order["totals"]["total"])) for order in todays_orders),
            start=Decimal("0.00"),
        )
        order_count = len(todays_orders)
        currency = (
            todays_orders[0]["totals"]["currency"]
            if todays_orders
            else self.default_currency
        )
        aov = (
            (total_sales / order_count).quantize(Decimal("0.01"))
            if order_count
            else Decimal("0.00")
        )
        return ChatbotReply(
            message=ResponseTemplates.admin_sales(
                self.store_name,
                order_count=order_count,
                total_sales=total_sales,
                average_order_value=aov,
                currency=currency,
            ),
            intent=intent,
            context=context,
            metadata={"order_count": order_count, "total_sales": str(total_sales)},
        )

    async def _handle_low_stock(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        threshold = intent.entities.stock_threshold or self.low_stock_threshold
        products = await self._get_products()
        low_stock = [product for product in products if product["stock"] <= threshold]
        cards = [
            format_product_card(product, product["currency"])
            for product in low_stock[:5]
        ]
        return ChatbotReply(
            message=ResponseTemplates.low_stock(self.store_name, low_stock[:5]),
            intent=intent,
            context=context,
            cards=cards,
            metadata={"threshold": threshold},
        )

    async def _handle_refund(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        if not intent.entities.order_ids:
            return self._simple_reply(
                "Tell me which order number you want refunded.", intent, context
            )
        order_id = intent.entities.order_ids[0]
        order = await self._get_order(order_id)
        updated = await self._update_order(order_id, {"status": "refunded"})
        normalized = self._normalize_order(updated or order)
        return ChatbotReply(
            message=ResponseTemplates.refund_processed(order_id, normalized["status"]),
            intent=intent,
            context=context,
            cards=[format_order_status(normalized)],
        )

    async def _handle_update_price(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        if intent.entities.price is None:
            return self._simple_reply(
                "Tell me the new price you want to set.", intent, context
            )
        product = await self._resolve_product(intent.entities.product_names, context)
        if product is None:
            return self._simple_reply(
                "I couldn't find that product to update yet.", intent, context
            )
        updated = await self._update_product(
            int(product["id"]),
            {
                "regular_price": f"{intent.entities.price:.2f}",
                "price": f"{intent.entities.price:.2f}",
            },
        )
        normalized = self._normalize_product(updated or product)
        normalized["price"] = intent.entities.price
        return ChatbotReply(
            message=ResponseTemplates.price_updated(
                normalized["name"],
                intent.entities.price,
                normalized["currency"],
            ),
            intent=intent,
            context=context,
            cards=[format_product_card(normalized, normalized["currency"])],
        )

    async def _handle_track_order(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        order: dict[str, Any] | None = None
        if intent.entities.order_ids:
            order = await self._get_order(intent.entities.order_ids[0])
        elif context.customer_id is not None:
            orders = await self._get_orders(customer=context.customer_id)
            order = orders[0] if orders else None
        if order is None:
            return self._simple_reply(
                "I couldn't find that order yet. Please share your order number.",
                intent,
                context,
            )
        normalized = self._normalize_order(order)
        context.last_order_id = int(normalized["id"])
        card = format_order_status(normalized)
        return ChatbotReply(
            message=ResponseTemplates.order_status(card),
            intent=intent,
            context=context,
            cards=[card],
        )

    async def _handle_return_item(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        order_id = (
            intent.entities.order_ids[0]
            if intent.entities.order_ids
            else context.last_order_id
        )
        policy = self.policy_provider("return_policy")
        return self._simple_reply(
            ResponseTemplates.return_guidance(policy, order_id),
            intent,
            context,
        )

    async def _handle_purchase_history(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        if context.customer_id is None:
            return self._simple_reply(
                "Sign in or share your customer account so I can fetch purchase history.",
                intent,
                context,
            )
        orders = await self._get_orders(customer=context.customer_id)
        total_spend = sum(
            (Decimal(str(order["totals"]["total"])) for order in orders),
            start=Decimal("0.00"),
        )
        currency = orders[0]["totals"]["currency"] if orders else self.default_currency
        cards = [format_order_status(order) for order in orders[:3]]
        return ChatbotReply(
            message=ResponseTemplates.purchase_history(
                len(orders), total_spend, currency
            ),
            intent=intent,
            context=context,
            cards=cards,
        )

    async def _handle_recommend_products(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        seed_names = list(intent.entities.product_names)
        if not seed_names and context.customer_id is not None:
            orders = await self._get_orders(customer=context.customer_id)
            if orders and orders[0]["items"]:
                seed_names = [orders[0]["items"][0]["name"]]
        if not seed_names:
            seed_names = list(context.last_product_names[:1])
        if not seed_names:
            return self._simple_reply(
                "Tell me a product you liked and I'll recommend similar items.",
                intent,
                context,
            )

        recommendations: list[dict[str, Any]] = []
        for seed_name in seed_names:
            recommendations.extend(await self._search_products(seed_name))
        deduped = self._dedupe_products(recommendations)
        if seed_names:
            lowered = {seed.lower() for seed in seed_names}
            deduped = [
                product for product in deduped if product["name"].lower() not in lowered
            ]
        if not deduped:
            catalog = await self._get_products()
            lowered = {seed.lower() for seed in seed_names}
            deduped = [
                product for product in catalog if product["name"].lower() not in lowered
            ]
        cards = [
            format_product_card(product, product["currency"]) for product in deduped[:3]
        ]
        return ChatbotReply(
            message=ResponseTemplates.recommendations(deduped[:3]),
            intent=intent,
            context=context,
            cards=cards,
        )

    async def _handle_product_availability(
        self,
        intent: IntentMatch,
        context: CommerceContext,
    ) -> ChatbotReply:
        search_terms = (
            intent.entities.product_names
            or context.last_product_names
            or context.browsing_history[:1]
        )
        products = await self._find_products(search_terms)
        if intent.entities.color:
            products = [
                product
                for product in products
                if self._matches_color(product, intent.entities.color)
            ]
        cards = [
            format_product_card(product, product["currency"])
            for product in products[:4]
        ]
        return ChatbotReply(
            message=ResponseTemplates.availability(products[:4], intent.entities.color),
            intent=intent,
            context=context,
            cards=cards,
        )

    async def _handle_return_policy(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        return self._simple_reply(
            self.policy_provider("return_policy"), intent, context
        )

    async def _handle_gift_search(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        budget = intent.entities.max_price or Decimal("50.00")
        products = [
            product
            for product in await self._get_products()
            if Decimal(str(product["price"])) <= budget and product["in_stock"]
        ]
        products.sort(key=lambda item: (Decimal(str(item["price"])), item["name"]))
        cards = [
            format_product_card(product, product["currency"])
            for product in products[:4]
        ]
        return ChatbotReply(
            message=ResponseTemplates.gift_guide(
                products[:4], budget, self.default_currency
            ),
            intent=intent,
            context=context,
            cards=cards,
        )

    async def _handle_compare_products(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        names = intent.entities.product_names or context.last_product_names[:2]
        if len(names) < 2:
            return self._simple_reply(
                "Tell me the two products you'd like compared.", intent, context
            )
        products = []
        for name in names[:2]:
            product = await self._resolve_product([name], context)
            if product is not None:
                products.append(product)
        if len(products) < 2:
            return self._simple_reply(
                "I couldn't find both products to compare.", intent, context
            )
        return ChatbotReply(
            message=ResponseTemplates.comparison(
                products[0],
                products[1],
                products[0]["currency"],
            ),
            intent=intent,
            context=context,
            cards=[
                format_product_card(product, product["currency"])
                for product in products
            ],
        )

    async def _handle_fallback(
        self, intent: IntentMatch, context: CommerceContext
    ) -> ChatbotReply:
        return self._simple_reply(
            ResponseTemplates.fallback(context.user_type.value), intent, context
        )

    def _simple_reply(
        self,
        message: str,
        intent: IntentMatch,
        context: CommerceContext,
    ) -> ChatbotReply:
        return ChatbotReply(message=message, intent=intent, context=context)

    async def _get_orders(self, *, customer: int | None = None) -> list[dict[str, Any]]:
        if self.woo_agent is None:
            return []
        params = {"per_page": 50}
        if customer is not None:
            params["customer"] = customer
        raw_orders = await self.woo_agent.get_orders(params=params)
        return [self._normalize_order(order) for order in raw_orders]

    async def _get_order(self, order_id: int) -> dict[str, Any]:
        if self.woo_agent is None:
            raise LookupError(
                f"order #{order_id} is unavailable without a WooCommerce agent"
            )
        return self._normalize_order(await self.woo_agent.get_order(order_id))

    async def _update_order(
        self, order_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if self.woo_agent is None or not hasattr(self.woo_agent, "update_order"):
            return None
        return await self.woo_agent.update_order(order_id, payload)

    async def _get_products(self) -> list[dict[str, Any]]:
        if self.woo_agent is None:
            return []
        raw_products = await self.woo_agent.get_products(params={"per_page": 100})
        return [self._normalize_product(product) for product in raw_products]

    async def _update_product(
        self, product_id: int, payload: dict[str, Any]
    ) -> dict[str, Any] | None:
        if self.woo_agent is None or not hasattr(self.woo_agent, "update_product"):
            return None
        return await self.woo_agent.update_product(product_id, payload)

    async def _search_products(self, query: str) -> list[dict[str, Any]]:
        if not query:
            return []
        if self.woo_agent is not None and hasattr(self.woo_agent, "search_products"):
            raw_products = await self.woo_agent.search_products(query)
            return [self._normalize_product(product) for product in raw_products]
        return [
            product
            for product in await self._get_products()
            if query.lower() in product["name"].lower()
        ]

    async def _find_products(self, names: list[str]) -> list[dict[str, Any]]:
        if not names:
            return await self._get_products()
        found: list[dict[str, Any]] = []
        for name in names:
            found.extend(await self._search_products(name))
        return self._dedupe_products(found)

    async def _resolve_product(
        self, names: list[str], context: CommerceContext
    ) -> dict[str, Any] | None:
        candidates = await self._find_products(names or context.last_product_names[:1])
        return candidates[0] if candidates else None

    def _normalize_product(self, product: dict[str, Any]) -> dict[str, Any]:
        stock = product.get("stock")
        if stock is None:
            stock = product.get("stock_quantity", 0) or 0
        price_value = product.get("price") or product.get("regular_price") or "0"
        image = None
        alt_text = None
        images = product.get("images") or []
        if images:
            first = images[0]
            image = first.get("src")
            alt_text = first.get("alt")
        return {
            "id": product.get("id"),
            "name": product.get("name", "Unnamed product"),
            "price": Decimal(str(price_value or "0")),
            "currency": str(product.get("currency") or self.default_currency).upper(),
            "description": product.get("description", "")
            or product.get("short_description", ""),
            "sku": product.get("sku"),
            "stock": int(stock),
            "in_stock": bool(product.get("in_stock", int(stock) > 0)),
            "permalink": product.get("permalink"),
            "image": image,
            "alt_text": alt_text,
            "attributes": product.get("attributes", []),
        }

    def _normalize_order(self, order: dict[str, Any]) -> dict[str, Any]:
        totals = order.get("totals") or {
            "subtotal": order.get("subtotal", order.get("total", "0")),
            "discount_total": order.get("discount_total", "0"),
            "shipping_total": order.get("shipping_total", "0"),
            "tax_total": order.get("total_tax", order.get("tax_total", "0")),
            "total": order.get("total", "0"),
            "currency": str(order.get("currency") or self.default_currency).upper(),
        }
        items = order.get("items") or order.get("line_items") or []
        return {
            "id": order.get("id"),
            "status": order.get("status", "unknown"),
            "date_created": order.get("date_created") or order.get("date_created_gmt"),
            "tracking_number": order.get("tracking_number"),
            "customer_note": order.get("customer_note"),
            "items": [
                {
                    "id": item.get("id"),
                    "name": item.get("name", "Item"),
                    "quantity": item.get("quantity", 1),
                    "total": item.get("total", item.get("subtotal", "0")),
                }
                for item in items
            ],
            "totals": {
                "subtotal": Decimal(str(totals.get("subtotal", "0"))),
                "discount_total": Decimal(str(totals.get("discount_total", "0"))),
                "shipping_total": Decimal(str(totals.get("shipping_total", "0"))),
                "tax_total": Decimal(str(totals.get("tax_total", "0"))),
                "total": Decimal(str(totals.get("total", order.get("total", "0")))),
                "currency": str(
                    totals.get("currency")
                    or order.get("currency")
                    or self.default_currency
                ).upper(),
            },
        }

    @staticmethod
    def _order_date(order: dict[str, Any]) -> datetime:
        raw_value = order.get("date_created")
        if isinstance(raw_value, datetime):
            return raw_value.astimezone(UTC)
        if not raw_value:
            return datetime.now(UTC)
        return datetime.fromisoformat(str(raw_value).replace("Z", "+00:00")).astimezone(
            UTC
        )

    @staticmethod
    def _matches_color(product: dict[str, Any], color: str) -> bool:
        haystacks = [product.get("name", ""), product.get("description", "")]
        for attribute in product.get("attributes", []):
            options = attribute.get("options") or []
            haystacks.extend(str(option) for option in options)
        return any(color.lower() in str(value).lower() for value in haystacks)

    @staticmethod
    def _dedupe_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[int | str | None] = set()
        deduped: list[dict[str, Any]] = []
        for product in products:
            key = product.get("id") or product.get("name")
            if key in seen:
                continue
            seen.add(key)
            deduped.append(product)
        return deduped

    @staticmethod
    def _default_policy_provider(policy_name: str) -> str:
        if policy_name == "return_policy":
            return (
                "Returns are accepted within 30 days for unused items in original condition. "
                "Refunds are sent back to the original payment method after inspection."
            )
        return "Support policy unavailable."


__all__ = [
    "ChatbotReply",
    "WooCommerceChatbot",
]
